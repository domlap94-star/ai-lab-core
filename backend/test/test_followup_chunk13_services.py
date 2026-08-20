import os
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import event, text

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)

DATABASE_NAME = "ai_lab_chunk13_20260820"
os.environ["POSTGRES_DB"] = DATABASE_NAME
require_test_database_environment(DATABASE_NAME)

from app.database.session import SessionLocal
from app.models.document import Document
from app.models.client import Client
from app.models.client_activity_event import ClientActivityEvent
from app.models.role import Role
from app.models.user import User
from app.schemas.work_item import AbsenceCreate, AbsenceReview, WorkItemCreate, WorkItemNoteCreate, WorkItemUpdate
from app.services.work_item_service import AbsenceAuthorizationError, AbsenceOverlapError, AbsenceService, CalendarService, WorkItemConflictError, WorkItemService
from app.services.timeline_service import TimelineService


def require(value: bool, message: str) -> None:
    if not value: raise AssertionError(message)


def main() -> None:
    db = SessionLocal()
    assert_isolated_database(db, DATABASE_NAME)
    suffix = uuid4().hex[:10]
    role = db.query(Role).filter(Role.name == "User").one()
    admin_role = db.query(Role).filter(Role.name == "Administrator").one_or_none()
    created_admin_role = admin_role is None
    if admin_role is None:
        admin_role = Role(name="Administrator", description="Isolated CHUNK 13 fixture")
        db.add(admin_role); db.flush()
    user = User(username=f"chunk13_{suffix}", email=f"chunk13-{suffix}@example.invalid", password_hash="x", is_active=True, role_id=role.id)
    admin = User(username=f"chunk13_admin_{suffix}", email=f"chunk13-admin-{suffix}@example.invalid", password_hash="x", is_active=True, role_id=admin_role.id)
    client = Client(client_type="company", name=f"CHUNK 13 synthetic {suffix}", country_code="PL")
    db.add_all((user, admin, client)); db.commit(); db.refresh(user); db.refresh(admin); db.refresh(client)
    service = WorkItemService(db)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    try: WorkItemCreate(item_type="task", title="Naive time", start_at=datetime(2026, 8, 20, 9))
    except ValueError: pass
    else: raise AssertionError("timezone-naive WorkItem timestamp accepted")
    before_failed_audit = db.execute(text("select count(*) from work_items")).scalar_one()
    failing_service = WorkItemService(db)
    failing_service.history.persist = lambda **_: (_ for _ in ()).throw(RuntimeError("synthetic audit failure"))
    try: failing_service.create(WorkItemCreate(item_type="task", title="Must roll back"), user)
    except RuntimeError: db.rollback()
    else: raise AssertionError("synthetic audit failure was ignored")
    require(db.execute(text("select count(*) from work_items")).scalar_one() == before_failed_audit, "audit failure did not roll back WorkItem")
    created = []
    for kind in ("task", "order", "realization", "reminder", "event"):
        item = service.create(WorkItemCreate(item_type=kind, title=f"Synthetic {kind}", start_at=now if kind != "reminder" else None, due_at=now + timedelta(hours=1), priority="normal", client_id=client.id if kind == "realization" else None), user)
        created.append(item)
    old_start_only = service.create(WorkItemCreate(item_type="task", title="Old start-only", start_at=now-timedelta(days=45)), user)
    created.append(old_start_only)
    require(len(created) == 6 and all(item.version == 1 for item in created), "all item types were not created")
    statements = []
    def count_statement(*args):
        statements.append(args[2])
    event.listen(db.bind, "before_cursor_execute", count_statement)
    try:
        page = service.list(client_id=client.id, skip=0, limit=50)
    finally:
        event.remove(db.bind, "before_cursor_execute", count_statement)
    require(page["total"] == 1, "Client list filter returned an unexpected result")
    require(len(statements) == 2, f"WorkItem list regressed to N+1 queries: {len(statements)}")
    updated = service.update(created[0].id, WorkItemUpdate(expected_version=1, status="completed"), user)
    require(updated.version == 2 and updated.completed_at is not None, "completion invariant failed")
    try: service.update(created[0].id, WorkItemUpdate(expected_version=1, title="stale"), user)
    except WorkItemConflictError: pass
    else: raise AssertionError("stale WorkItem update accepted")
    note = service.create_note(created[0].id, WorkItemNoteCreate(text="Synthetic dictated note"), user)
    require(note.text == "Synthetic dictated note", "note create failed")
    document = Document(filename=f"chunk13-{suffix}.jpg", original_filename="synthetic.jpg", content_type="image/jpeg", file_size=10, source_type="manual_upload", external_id=f"chunk13-{suffix}")
    db.add(document); db.commit(); db.refresh(document)
    link = service.link_document(created[0].id, document.id, note.id, user)
    require(link.document_id == document.id and len(service.list_documents(created[0].id)) == 1, "document relation failed")
    service.link_document(created[2].id, document.id, None, user)
    require(service.list(client_id=client.id)["total"] == 1, "Client realization projection failed")
    activity_before = db.query(ClientActivityEvent).count()
    timeline = TimelineService(db).get_client_timeline(client_id=client.id, skip=0, limit=50)
    require(any(event.event_type == "realization_created" for event in timeline.items), "Client Timeline omitted realization")
    require(db.query(ClientActivityEvent).count() == activity_before, "derived timeline persisted duplicate Activity")
    absences = AbsenceService(db)
    absence = absences.create(AbsenceCreate(absence_type="vacation", start_date=date.today()+timedelta(days=2), end_date=date.today()+timedelta(days=3)), user)
    try: absences.create(AbsenceCreate(absence_type="day_off", start_date=absence.start_date, end_date=absence.end_date), user)
    except AbsenceOverlapError: pass
    else: raise AssertionError("overlapping absence accepted")
    approved = absences.review(absence.id, absence.version, None, admin, approved=True)
    require(approved.status == "approved", "admin approval failed")
    own = absences.create(AbsenceCreate(absence_type="other", start_date=date.today()+timedelta(days=10), end_date=date.today()+timedelta(days=10)), admin)
    try: absences.review(own.id, own.version, None, user, approved=True)
    except AbsenceAuthorizationError: pass
    else: raise AssertionError("non-admin absence approval accepted")
    try: absences.review(own.id, own.version, None, admin, approved=True)
    except AbsenceAuthorizationError: pass
    else: raise AssertionError("self approval accepted")
    month = CalendarService(db).month(now.year, now.month, admin)
    require(any(item.entity_id == created[0].id for item in month.items), "calendar projection omitted work item")
    require(not any(item.entity_id == old_start_only.id for item in month.items), "start-only item leaked into a later month")
    # Exact isolated-fixture cleanup, including truthful test-only audit rows.
    ids = [item.id for item in created]
    absence_ids = [absence.id, own.id]
    db.execute(text("delete from change_history_events where actor_user_id in (:u,:a)"), {"u": user.id, "a": admin.id})
    db.execute(text("delete from work_item_documents where work_item_id = any(:ids)"), {"ids": ids})
    db.execute(text("delete from work_item_notes where work_item_id = any(:ids)"), {"ids": ids})
    db.execute(text("delete from work_items where id = any(:ids)"), {"ids": ids})
    db.execute(text("delete from absence_requests where id = any(:ids)"), {"ids": absence_ids})
    db.delete(document); db.delete(client); db.delete(user); db.delete(admin); db.flush()
    if created_admin_role: db.delete(admin_role)
    db.commit(); db.close()
    print("CHUNK 13 services: PASS")


if __name__ == "__main__": main()
