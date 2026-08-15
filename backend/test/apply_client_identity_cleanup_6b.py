from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.repositories.client_email_repository import ClientEmailRepository
from app.services.client_identity_cleanup_dry_run_service import (
    ClientIdentityCleanupDryRunService,
)
from app.services.client_identity_name_quality_service import (
    ClientIdentityNameQualityService,
)


REPORT_DIR = Path(__file__).resolve().parent / "reports"
DEFAULT_MANIFEST = REPORT_DIR / "client_identity_cleanup_approved_apply.json"
BEFORE_PATH = REPORT_DIR / "client_identity_cleanup_6b_before.json"
AFTER_PATH = REPORT_DIR / "client_identity_cleanup_6b_after.json"
ROLLBACK_PATH = REPORT_DIR / "client_identity_cleanup_6b_rollback.json"

APPROVAL_SCOPE = "CHUNK_6B_EXACT_SIX_RENAMES"
EXPECTED_CLIENT_IDS = (39, 113, 1912, 1915, 2269, 2282)
EXPECTED_MANIFEST_SHA256 = (
    "2bf293e40c13990134dc0a92793a923d652df801ad9395f8aa4ff28d2ece3533"
)
HOLD_CLIENT_IDS = (13, 1745, 2256, 2560)
SNAPSHOT_FIELDS = (
    "client_id",
    "name",
    "client_type",
    "legal_name",
    "primary_email",
    "primary_phone",
    "tax_id",
    "street",
    "building_number",
    "unit_number",
    "postal_code",
    "city",
    "country_code",
    "notes_state",
    "notes_sha256",
    "deleted_at",
    "updated_at",
)
UNCHANGED_FIELDS = tuple(
    field for field in SNAPSHOT_FIELDS if field not in {"name", "updated_at"}
)


class ControlledApplyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApprovedRename:
    client_id: int
    expected_old_name: str
    approved_new_name: str


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def load_approval_manifest(path: Path) -> list[ApprovedRename]:
    raw = path.read_bytes()
    if _sha256_bytes(raw) != EXPECTED_MANIFEST_SHA256:
        raise ControlledApplyError("Approval manifest SHA256 mismatch")
    return validate_approval_manifest(json.loads(raw.decode("utf-8")))


def validate_approval_manifest(payload: dict[str, Any]) -> list[ApprovedRename]:
    if payload.get("approval_scope") != APPROVAL_SCOPE:
        raise ControlledApplyError("Unexpected approval scope")
    if payload.get("approved_count") != len(EXPECTED_CLIENT_IDS):
        raise ControlledApplyError("Approval manifest count must equal six")
    records = payload.get("records")
    if not isinstance(records, list) or len(records) != len(EXPECTED_CLIENT_IDS):
        raise ControlledApplyError("Approval manifest must contain six records")
    allowed_keys = {"client_id", "expected_old_name", "approved_new_name"}
    if any(set(record) != allowed_keys for record in records):
        raise ControlledApplyError("Approval manifest record shape is invalid")
    approvals = [ApprovedRename(**record) for record in records]
    ids = tuple(item.client_id for item in approvals)
    if ids != EXPECTED_CLIENT_IDS or len(set(ids)) != len(ids):
        raise ControlledApplyError("Approval manifest contains unexpected client IDs")
    if any(
        not item.expected_old_name.strip() or not item.approved_new_name.strip()
        for item in approvals
    ):
        raise ControlledApplyError("Approval names must be non-empty")
    return approvals


def validate_client_rows(
    approvals: list[ApprovedRename],
    clients: list[Client],
) -> None:
    by_id = {client.id: client for client in clients}
    if set(by_id) != {item.client_id for item in approvals}:
        raise ControlledApplyError("Exactly six active target clients are required")
    for approval in approvals:
        client = by_id[approval.client_id]
        if client.deleted_at is not None:
            raise ControlledApplyError(f"Client {client.id} is not active")
        if client.name != approval.expected_old_name:
            raise ControlledApplyError(
                f"Client {client.id} OLD name mismatch: {client.name!r}"
            )


def validate_dry_run_proposals(approvals, proposals) -> None:
    by_id = {proposal.client_id: proposal for proposal in proposals}
    for approval in approvals:
        proposal = by_id.get(approval.client_id)
        if proposal is None:
            raise ControlledApplyError(
                f"Client {approval.client_id} is missing from current dry-run"
            )
        if proposal.action != "SAFE_RENAME_CANDIDATE":
            raise ControlledApplyError(
                f"Client {approval.client_id} is no longer SAFE"
            )
        if proposal.proposed_name != approval.approved_new_name:
            raise ControlledApplyError(
                f"Client {approval.client_id} proposed name mismatch"
            )
        if proposal.duplicate_risk != "NONE":
            raise ControlledApplyError(
                f"Client {approval.client_id} duplicate risk is not NONE"
            )
        if not proposal.identity_support_evidence:
            raise ControlledApplyError(
                f"Client {approval.client_id} lacks identity support evidence"
            )
        if proposal.conflicts:
            raise ControlledApplyError(
                f"Client {approval.client_id} has projection conflicts"
            )
        if ClientIdentityNameQualityService.suspicion_types(
            proposal.proposed_name
        ) or ClientIdentityNameQualityService.additional_findings(
            proposal.proposed_name
        ):
            raise ControlledApplyError(
                f"Client {approval.client_id} proposed name fails quality gates"
            )


def assign_approved_names(
    approvals: list[ApprovedRename],
    clients: list[Client],
) -> None:
    validate_client_rows(approvals, clients)
    by_id = {client.id: client for client in clients}
    for approval in approvals:
        by_id[approval.client_id].name = approval.approved_new_name


def snapshot_client(client: Client) -> dict[str, Any]:
    notes = client.notes
    return {
        "client_id": client.id,
        "name": client.name,
        "client_type": client.client_type,
        "legal_name": client.legal_name,
        "primary_email": client.primary_email,
        "primary_phone": client.primary_phone,
        "tax_id": client.tax_id,
        "street": client.street,
        "building_number": client.building_number,
        "unit_number": client.unit_number,
        "postal_code": client.postal_code,
        "city": client.city,
        "country_code": client.country_code,
        "notes_state": "null" if notes is None else "value",
        "notes_sha256": (
            None if notes is None else _sha256_bytes(notes.encode("utf-8"))
        ),
        "deleted_at": client.deleted_at.isoformat() if client.deleted_at else None,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }


def relationship_snapshot(db: Session, client_ids) -> dict[str, Any]:
    result: dict[str, Any] = {}
    email_repository = ClientEmailRepository(db)
    for client_id in client_ids:
        document_ids = [
            row[0]
            for row in db.query(Document.id)
            .filter(Document.client_id == client_id)
            .order_by(Document.id.asc())
            .all()
        ]
        candidate_ids = [
            row[0]
            for row in db.query(ClientCandidate.id)
            .filter(
                ClientCandidate.matched_client_id == client_id,
                ClientCandidate.deleted_at.is_(None),
            )
            .order_by(ClientCandidate.id.asc())
            .all()
        ]
        _, email_total = email_repository.get_page(
            client_id=client_id,
            skip=0,
            limit=1,
        )
        result[str(client_id)] = {
            "document_count": len(document_ids),
            "document_ids": document_ids,
            "email_history_count": email_total,
            "matched_candidate_ids": candidate_ids,
        }
    return result


def quality_counts(db: Session) -> dict[str, int]:
    clients = db.query(Client).filter(Client.deleted_at.is_(None)).all()
    quality = ClientIdentityNameQualityService
    categories = [quality.suspicion_types(client.name) for client in clients]
    return {
        "active_clients": len(clients),
        "email_as_name": sum("EMAIL_AS_NAME" in item for item in categories),
        "phone_as_name": sum("PHONE_AS_NAME" in item for item in categories),
        "file_as_name": sum("FILE_AS_NAME" in item for item in categories),
        "suspicious_unique": sum(bool(item) for item in categories),
    }


def hold_names(db: Session) -> dict[str, str]:
    rows = (
        db.query(Client.id, Client.name)
        .filter(Client.id.in_(HOLD_CLIENT_IDS))
        .order_by(Client.id.asc())
        .all()
    )
    if tuple(row.id for row in rows) != HOLD_CLIENT_IDS:
        raise ControlledApplyError("HOLD client set is incomplete")
    return {str(row.id): row.name for row in rows}


def build_snapshot(db: Session, clients: list[Client]) -> dict[str, Any]:
    records = [snapshot_client(client) for client in clients]
    relationships = relationship_snapshot(db, [client.id for client in clients])
    content = {
        "records": records,
        "relationships": relationships,
        "quality": quality_counts(db),
        "hold_names": hold_names(db),
    }
    return {**content, "snapshot_sha256": _canonical_sha256(content)}


def validate_snapshot_diff(before: dict[str, Any], after: dict[str, Any]) -> None:
    before_rows = {row["client_id"]: row for row in before["records"]}
    after_rows = {row["client_id"]: row for row in after["records"]}
    if set(before_rows) != set(after_rows) or len(before_rows) != 6:
        raise ControlledApplyError("Snapshot target set changed")
    for client_id in before_rows:
        for field in UNCHANGED_FIELDS:
            if before_rows[client_id][field] != after_rows[client_id][field]:
                raise ControlledApplyError(
                    f"Unexpected field change for client {client_id}: {field}"
                )
    if before["relationships"] != after["relationships"]:
        raise ControlledApplyError("Client relationship integrity changed")
    if before["hold_names"] != after["hold_names"]:
        raise ControlledApplyError("A HOLD client name changed")


def validate_quality_delta(before, after, approvals) -> None:
    quality = ClientIdentityNameQualityService
    keys = {
        "EMAIL_AS_NAME": "email_as_name",
        "PHONE_AS_NAME": "phone_as_name",
        "FILE_AS_NAME": "file_as_name",
    }
    expected = dict(before)
    for approval in approvals:
        old_types = set(quality.suspicion_types(approval.expected_old_name))
        new_types = set(quality.suspicion_types(approval.approved_new_name))
        for category, key in keys.items():
            expected[key] += int(category in new_types) - int(category in old_types)
        expected["suspicious_unique"] += int(bool(new_types)) - int(bool(old_types))
    if after != expected:
        raise ControlledApplyError(
            f"Global quality delta does not match approval scope: {after!r}"
        )


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _target_clients(db: Session, approvals, *, lock: bool) -> list[Client]:
    query = (
        db.query(Client)
        .filter(
            Client.id.in_([item.client_id for item in approvals]),
            Client.deleted_at.is_(None),
        )
        .order_by(Client.id.asc())
    )
    if lock:
        query = query.with_for_update()
    return query.all()


def execute(*, apply: bool = False, manifest_path: Path = DEFAULT_MANIFEST) -> None:
    approvals = load_approval_manifest(manifest_path)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    before: dict[str, Any] | None = None
    try:
        if not apply:
            db.execute(text("SET TRANSACTION READ ONLY"))
        proposals, _ = ClientIdentityCleanupDryRunService(db).run()
        validate_dry_run_proposals(approvals, proposals)
        clients = _target_clients(db, approvals, lock=apply)
        validate_client_rows(approvals, clients)
        before = build_snapshot(db, clients)
        _write_json(BEFORE_PATH, before)

        print(f"WOULD CHANGE: {len(approvals)}")
        for approval in approvals:
            print(
                f"{approval.client_id}: {approval.expected_old_name} -> "
                f"{approval.approved_new_name}"
            )

        if not apply:
            db.rollback()
            print("MODE: DRY RUN")
            print("database modifications: 0")
            return

        assign_approved_names(approvals, clients)
        dirty_client_ids = {
            item.id for item in db.dirty if isinstance(item, Client)
        }
        if dirty_client_ids != set(EXPECTED_CLIENT_IDS):
            raise ControlledApplyError(
                f"Unexpected dirty Client set: {sorted(dirty_client_ids)}"
            )
        if any(not isinstance(item, Client) for item in db.dirty):
            raise ControlledApplyError("A non-Client ORM record became dirty")
        db.flush()
        for client, approval in zip(clients, approvals, strict=True):
            if client.name != approval.approved_new_name:
                raise ControlledApplyError(
                    f"Client {client.id} failed post-flush name verification"
                )
        in_transaction_after = build_snapshot(db, clients)
        validate_snapshot_diff(before, in_transaction_after)
        db.commit()
        print("TRANSACTION: COMMITTED")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    verify = SessionLocal()
    try:
        verify.execute(text("SET TRANSACTION READ ONLY"))
        clients = (
            verify.query(Client)
            .filter(Client.id.in_(EXPECTED_CLIENT_IDS))
            .order_by(Client.id.asc())
            .all()
        )
        after = build_snapshot(verify, clients)
        validate_snapshot_diff(before, after)
        validate_quality_delta(before["quality"], after["quality"], approvals)
        approvals_by_id = {item.client_id: item for item in approvals}
        for client in clients:
            if client.name != approvals_by_id[client.id].approved_new_name:
                raise ControlledApplyError(
                    f"Client {client.id} failed committed name verification"
                )
        _write_json(AFTER_PATH, after)
        _write_json(
            ROLLBACK_PATH,
            {
                "approval_scope": APPROVAL_SCOPE,
                "records": [
                    {
                        "client_id": item.client_id,
                        "current_expected_new_name": item.approved_new_name,
                        "rollback_old_name": item.expected_old_name,
                    }
                    for item in approvals
                ],
            },
        )
        print("POST-COMMIT SNAPSHOT: VERIFIED")
        print("changed target clients: 6")
    finally:
        verify.rollback()
        verify.close()


def verify_api(manifest_path: Path = DEFAULT_MANIFEST) -> None:
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app
    from app.models.user import User

    approvals = load_approval_manifest(manifest_path)
    http = TestClient(app)
    if http.get(f"/api/v1/clients/{approvals[0].client_id}").status_code != 401:
        raise ControlledApplyError("Anonymous Client detail auth changed")
    db = SessionLocal()
    try:
        db.execute(text("SET TRANSACTION READ ONLY"))
        user = db.query(User).filter(User.is_active.is_(True)).first()
        if user is None:
            raise ControlledApplyError("No active user for API verification")
        headers = {
            "Authorization": "Bearer "
            + create_access_token(data={"sub": user.username})
        }
        for approval in approvals:
            detail = http.get(
                f"/api/v1/clients/{approval.client_id}", headers=headers
            )
            if detail.status_code != 200:
                raise ControlledApplyError(
                    f"Client {approval.client_id} detail returned {detail.status_code}"
                )
            if detail.json()["name"] != approval.approved_new_name:
                raise ControlledApplyError(
                    f"Client {approval.client_id} detail name mismatch"
                )
            page = http.get(
                "/api/v1/clients/page",
                headers=headers,
                params={"search": approval.approved_new_name, "limit": 100},
            )
            if page.status_code != 200:
                raise ControlledApplyError(
                    f"Client {approval.client_id} page search returned "
                    f"{page.status_code}"
                )
            matches = [
                item
                for item in page.json()["items"]
                if item["id"] == approval.client_id
                and item["name"] == approval.approved_new_name
            ]
            if len(matches) != 1:
                raise ControlledApplyError(
                    f"Client {approval.client_id} was not found by approved name"
                )
            print(f"API VERIFIED: {approval.client_id} -> {approval.approved_new_name}")
        print("CLIENT DETAIL + PAGINATED NAME SEARCH: OK")
        print("AUTH 401: OK")
    finally:
        db.rollback()
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify-api", action="store_true")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    if args.verify_api:
        verify_api(args.manifest)
    else:
        execute(apply=args.apply, manifest_path=args.manifest)


if __name__ == "__main__":
    main()
