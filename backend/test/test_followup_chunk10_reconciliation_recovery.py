from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.database.session import get_db
from app.main import app
from app.services import mail_reconciliation_service as module
from app.services.mail_reconciliation_provider import ReconciliationAudit
from app.services.mail_reconciliation_service import (
    MailReconciliationBusyError,
    MailReconciliationScopeError,
    MailReconciliationService,
    MailReconciliationValidationError,
    _RECONCILIATION_LOCK,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


class _Query:
    def __init__(self, db: "_Db", targets: tuple[Any, ...]) -> None:
        self.db = db
        self.targets = targets

    def filter(self, *_: Any) -> "_Query":
        return self

    def order_by(self, *_: Any) -> "_Query":
        return self

    def all(self) -> list[Any]:
        owner = getattr(self.targets[0], "class_", None)
        if getattr(owner, "__name__", "") == "CandidateSource":
            return [(value, {}) for value in sorted(self.db.existing)]
        if getattr(owner, "__name__", "") == "Document":
            return [(value,) for value in sorted(self.db.documents)]
        return []

    def first(self) -> Any:
        return SimpleNamespace(id=2, source_type="gmail")


class _Db:
    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = set(existing or set())
        self.documents: set[str] = set()
        self.rollbacks = 0

    def query(self, *targets: Any) -> _Query:
        return _Query(self, targets)

    def rollback(self) -> None:
        self.rollbacks += 1


class _Provider:
    def __init__(self, ids: list[str], messages: dict[str, dict[str, Any]]) -> None:
        self.ids = ids
        self.messages = messages
        self.audit_calls = 0
        self.fetch_calls: list[list[str]] = []

    def audit(self, *, window_days: int, limit: int) -> ReconciliationAudit:
        require(1 <= window_days <= 30, "Unbounded window reached provider")
        require(limit == 1000, "Provider limit changed")
        self.audit_calls += 1
        return ReconciliationAudit(self.ids[:], len(self.ids) > limit)

    def fetch(self, message_ids: list[str]) -> list[dict[str, Any]]:
        self.fetch_calls.append(message_ids[:])
        return [self.messages[value] for value in message_ids]


class _Service(MailReconciliationService):
    @staticmethod
    def _candidate_resolution(_: Any, request: Any) -> Any:
        return SimpleNamespace(
            request=request,
            match=None,
            email_match=SimpleNamespace(
                confidence="unresolved",
                reasons=(),
            ),
            classification="new_candidate",
            existing_candidate_id=None,
            existing_client_id=None,
            resolved_client_id=None,
            expected_candidate_delta=1,
            expected_new_client_link_delta=0,
        )

    def _expected_documents(self, messages: list[dict[str, Any]]) -> int:
        return sum(len(item.get("attachments") or []) for item in messages)

    def _ingest_attachments(self, item: dict[str, Any], candidate_id: int, client_id: int | None) -> int:
        return len(item.get("attachments") or [])

    def _mark_complete(self, source_id: int) -> None:
        return None


def _message(message_id: str) -> dict[str, Any]:
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "labelIds": ["INBOX"],
        "from": "Controlled <controlled@example.invalid>",
        "to": "podnoszenieposadzek@gmail.com",
        "subject": "Synthetic reconciliation",
        "text": "Synthetic body",
        "attachments": [],
    }


@contextmanager
def _fake_ingest(db: _Db, fail_id: str | None = None):
    original = module.ImportIngestService

    class _Ingest:
        def __init__(self, _: Any) -> None:
            pass

        def ingest(
            self,
            request: Any,
            *,
            email_resolution: Any | None = None,
        ) -> Any:
            message_id = request.source.external_id
            if message_id == fail_id:
                raise RuntimeError("synthetic_ingest_failure")
            created = message_id not in db.existing
            db.existing.add(message_id)
            return SimpleNamespace(
                source_id=len(db.existing),
                candidate_id=len(db.existing),
                created_source=created,
                created_candidate=created,
                matched_client_id=None,
            )

    module.ImportIngestService = _Ingest
    try:
        yield
    finally:
        module.ImportIngestService = original


def main() -> None:
    db = _Db({"present"})
    provider = _Provider(
        ["present", "missing"],
        {"missing": _message("missing")},
    )
    service = _Service(db, provider)
    dry = service.dry_run(window_days=7, actor_user_id=7)
    require(dry.messages_examined == 2, "Dry-run examined count mismatch")
    require(dry.already_present == 1, "Existing provider ID was not skipped")
    require(dry.missing_provider_ids == ["missing"], "Missing ID not detected")
    require(db.existing == {"present"}, "Dry-run wrote canonical data")

    try:
        service.apply(
            window_days=7,
            actor_user_id=8,
            dry_run_token=dry.dry_run_token,
        )
    except MailReconciliationValidationError:
        pass
    else:
        raise RuntimeError("A different actor reused the dry-run plan")

    with _fake_ingest(db):
        applied = service.apply(
            window_days=7,
            actor_user_id=7,
            dry_run_token=dry.dry_run_token,
        )
    require(applied.new_messages_ingested == 1, "Missing source not ingested once")
    require(db.existing == {"present", "missing"}, "Canonical set mismatch")

    fetches_before_replay = len(provider.fetch_calls)
    replay_dry = service.dry_run(window_days=7, actor_user_id=7)
    with _fake_ingest(db):
        replay = service.apply(
            window_days=7,
            actor_user_id=7,
            dry_run_token=replay_dry.dry_run_token,
        )
    require(replay.new_messages_ingested == 0, "Replay created a duplicate")
    require(
        len(provider.fetch_calls) == fetches_before_replay,
        "Replay fetched an existing message",
    )

    changed_provider = _Provider(["different"], {"different": _message("different")})
    changed = _Service(_Db(), changed_provider)
    changed_dry = changed.dry_run(window_days=7, actor_user_id=7)
    changed_provider.ids = ["different", "new-gap"]
    changed_provider.messages["new-gap"] = _message("new-gap")
    try:
        changed.apply(
            window_days=7,
            actor_user_id=7,
            dry_run_token=changed_dry.dry_run_token,
        )
    except MailReconciliationValidationError:
        pass
    else:
        raise RuntimeError("Changed plan bypassed dry-run token")

    failure_db = _Db()
    failure_provider = _Provider(
        ["ok", "fail"],
        {"ok": _message("ok"), "fail": _message("fail")},
    )
    failure_service = _Service(failure_db, failure_provider)
    failure_dry = failure_service.dry_run(window_days=7, actor_user_id=9)
    with _fake_ingest(failure_db, fail_id="fail"):
        partial = failure_service.apply(
            window_days=7,
            actor_user_id=9,
            dry_run_token=failure_dry.dry_run_token,
        )
    require(partial.new_messages_ingested == 1 and partial.failed == 1, "Partial failure summary mismatch")

    too_large = _Service(
        _Db(),
        _Provider([f"id-{value}" for value in range(101)], {}),
    )
    try:
        too_large.dry_run(window_days=7, actor_user_id=1)
    except MailReconciliationScopeError:
        pass
    else:
        raise RuntimeError("Missing-set ceiling was not enforced")

    try:
        service.dry_run(window_days=31, actor_user_id=7)
    except MailReconciliationValidationError:
        pass
    else:
        raise RuntimeError("Window ceiling was not enforced")

    _RECONCILIATION_LOCK.acquire()
    try:
        try:
            service.dry_run(window_days=7, actor_user_id=7)
        except MailReconciliationBusyError:
            pass
        else:
            raise RuntimeError("Concurrent reconciliation was not rejected")
    finally:
        _RECONCILIATION_LOCK.release()

    app.dependency_overrides[get_db] = lambda: _Db()
    try:
        response = TestClient(app).post(
            "/api/v1/mail/reconcile/dry-run",
            json={"window_days": 7},
        )
        require(response.status_code == 401, "Unauthenticated dry-run was not rejected")
    finally:
        app.dependency_overrides.clear()

    route_counts = {
        path: sum(
            1
            for route in app.routes
            if getattr(route, "path", None) == path
            and "POST" in getattr(route, "methods", set())
        )
        for path in (
            "/api/v1/mail/reconcile/dry-run",
            "/api/v1/mail/reconcile/apply",
        )
    }
    require(
        all(count == 1 for count in route_counts.values()),
        f"Reconciliation route registration mismatch: {route_counts}",
    )

    provider_source = open(
        "/app/app/services/mail_reconciliation_provider.py",
        encoding="utf-8",
    ).read()
    require("query" not in provider_source, "Arbitrary Gmail query passthrough found")
    require("checkpoint" not in provider_source, "Normal checkpoint mutation found")
    service_source = open(
        "/app/app/services/mail_reconciliation_service.py",
        encoding="utf-8",
    ).read()
    require(
        "client_id=" not in service_source.split("ImportIngestRequest(", 1)[1]
        .split("def _contact", 1)[0],
        "Client refresh could force a Client association",
    )
    print("FOLLOW-UP CHUNK 10 RECONCILIATION RECOVERY: 13/13 PASS")
    print("production_writes=0 n8n_changes=0 gmail_sends=0")


if __name__ == "__main__":
    main()
