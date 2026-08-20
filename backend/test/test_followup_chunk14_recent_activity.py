from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from time import perf_counter
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.engine import engine
from app.database.session import get_db
from app.main import app
from app.models.absence_request import AbsenceRequest
from app.models.change_history_event import ChangeHistoryEvent
from app.models.client import Client
from app.models.client_activity_event import ClientActivityEvent
from app.models.document import Document
from app.models.role import Role
from app.models.user import User
from app.models.work_item import WorkItem
from app.services.recent_activity_service import RecentActivityService


ISOLATED_DB_NAME = "ai_lab_chunk13_20260820"


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    require(
        os.getenv("POSTGRES_DB") == ISOLATED_DB_NAME,
        "CHUNK 14 tests require the explicitly isolated CHUNK 13 database",
    )
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
    suffix = uuid4().hex[:10]
    admin_role = db.query(Role).filter(Role.name == "Administrator").one_or_none()
    user_role = db.query(Role).filter(Role.name == "User").one_or_none()
    if admin_role is None:
        admin_role = Role(name="Administrator", description="CHUNK 14 isolated fixture")
        db.add(admin_role)
    if user_role is None:
        user_role = Role(name="User", description="CHUNK 14 isolated fixture")
        db.add(user_role)
    db.flush()
    admin = User(username=f"chunk14-admin-{suffix}", email=f"chunk14-admin-{suffix}@example.invalid", password_hash="x", is_active=True, role_id=admin_role.id)
    user = User(username=f"chunk14-user-{suffix}", email=f"chunk14-user-{suffix}@example.invalid", password_hash="x", is_active=True, role_id=user_role.id)
    other = User(username=f"chunk14-other-{suffix}", email=f"chunk14-other-{suffix}@example.invalid", password_hash="x", is_active=True, role_id=user_role.id)
    client = Client(client_type="company", name=f"CHUNK14 synthetic {suffix}", country_code="PL")
    db.add_all((admin, user, other, client))
    db.flush()
    now = datetime.now(UTC).replace(microsecond=0)
    work = WorkItem(item_type="task", title="Synthetic safe task", status="todo", priority="normal", created_by_user_id=user.id, updated_by_user_id=user.id, created_at=now, updated_at=now, version=1)
    db.add(work)
    db.flush()
    absence = AbsenceRequest(requester_user_id=other.id, absence_type="sick_leave", start_date=now.date(), end_date=now.date(), status="requested", version=1)
    document = Document(filename=f"chunk14-{suffix}.jpg", original_filename="safe-image.jpg", content_type="image/jpeg", file_size=10, source_type="manual_upload", external_id=f"chunk14-{suffix}", client_id=client.id, created_at=now - timedelta(seconds=3), updated_at=now - timedelta(seconds=3))
    db.add_all((absence, document))
    db.flush()

    activity = ClientActivityEvent(client_id=client.id, actor_user_id=user.id, event_type="client_status_changed", entity_type="client", entity_id=client.id, occurred_at=now + timedelta(seconds=5), event_metadata={"new_status": "completed"}, source_key=f"chunk14-activity-{suffix}")
    duplicate = ChangeHistoryEvent(actor_user_id=user.id, entity_type="client_workflow_status", entity_id=client.id, action="status_changed", changed_fields=["status"], before_values={"status": "untouched"}, after_values={"status": "completed"}, source_key=f"chunk14-change-duplicate-{suffix}", created_at=now + timedelta(seconds=4))
    note_history = ChangeHistoryEvent(actor_user_id=user.id, entity_type="work_item_note", entity_id=9000001, action="created", changed_fields=["work_item_id", "text"], before_values={}, after_values={"work_item_id": work.id, "text": {"length": 31, "sha256": "not-a-secret"}}, source_key=f"chunk14-note-{suffix}", created_at=now + timedelta(seconds=3))
    absence_history = ChangeHistoryEvent(actor_user_id=other.id, entity_type="absence_request", entity_id=absence.id, action="created", changed_fields=["note"], before_values={}, after_values={"note": {"length": 29, "sha256": "private-reason-not-content"}}, source_key=f"chunk14-absence-{suffix}", created_at=now + timedelta(seconds=2))
    user_history = ChangeHistoryEvent(actor_user_id=admin.id, entity_type="user", entity_id=other.id, action="updated", changed_fields=["email"], before_values={"email": {"masked": "o***@example.invalid"}}, after_values={"email": {"masked": "n***@example.invalid"}}, source_key=f"chunk14-user-{suffix}", created_at=now + timedelta(seconds=1))
    db.add_all((activity, duplicate, note_history, absence_history, user_history))
    db.flush()

    statements: list[str] = []
    def count_statement(*args) -> None:
        statements.append(args[2])
    event.listen(connection, "before_cursor_execute", count_statement)
    started = perf_counter()
    try:
        normal_page = RecentActivityService(db).get_page(viewer=user, limit=8)
    finally:
        elapsed_ms = (perf_counter() - started) * 1000
        event.remove(connection, "before_cursor_execute", count_statement)
    require(len(statements) <= 15, f"activity projection regressed to N+1 queries: {len(statements)}")
    require(elapsed_ms < 1000, f"isolated projection exceeded one second: {elapsed_ms:.1f} ms")
    require(all(normal_page.items[index].timestamp >= normal_page.items[index + 1].timestamp for index in range(len(normal_page.items) - 1)), "activity is not newest-first")
    require(sum(item.entity_type == "client" and item.entity_id == client.id and item.action == "status_changed" for item in normal_page.items) == 1, "canonical activity/change-history duplicate was not suppressed")
    require(any(item.entity_type == "work_item_note" and item.deep_link == f"/tasks/{work.id}" for item in normal_page.items), "work-item note activity/deep link missing")
    require(not any(item.entity_type == "absence_request" for item in normal_page.items), "normal user saw another employee absence activity")
    require(not any(item.entity_type == "user" for item in normal_page.items), "normal user saw admin-only user activity")
    encoded = " ".join(item.summary for item in normal_page.items)
    for forbidden in ("private-reason", "not-a-secret", "example.invalid"):
        require(forbidden not in encoded, f"private payload leaked into summary: {forbidden}")
    require(all(len(item.summary) <= 200 for item in normal_page.items), "summary bound exceeded")

    admin_page = RecentActivityService(db).get_page(viewer=admin, limit=50)
    require(any(item.entity_type == "absence_request" for item in admin_page.items), "admin absence activity missing")
    require(any(item.entity_type == "user" for item in admin_page.items), "admin user activity missing")
    require(RecentActivityService(db).get_page(viewer=admin, limit=1).has_more, "bounded has_more contract missing")

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    response = TestClient(app).get("/api/v1/activity/recent", params={"limit": 8})
    require(response.status_code == 200 and response.json()["limit"] == 8, "authenticated activity endpoint failed")
    app.dependency_overrides.clear()
    unauthenticated = TestClient(app).get("/api/v1/activity/recent")
    require(unauthenticated.status_code == 401, "activity endpoint accepted unauthenticated request")

    db.close()
    transaction.rollback()
    connection.close()
    print(f"CHUNK 14 recent activity: PASS; queries={len(statements)}; elapsed_ms={elapsed_ms:.1f}")


if __name__ == "__main__":
    main()
