from __future__ import annotations

import os
from datetime import datetime

os.environ.setdefault("POSTGRES_DB", "ai_lab_chunk13_20260820")

from test.support.database_safety import require_test_database_environment

EXPECTED_DB = os.environ["POSTGRES_DB"]
require_test_database_environment(EXPECTED_DB)

from app.database.session import SessionLocal, engine
from app.models.client import Client
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.models.work_item import WorkItem
from app.models.work_item_document import WorkItemDocument
from app.schemas.work_item import WorkItemCreate, WorkItemUpdate
from app.services.work_item_service import CalendarService, WorkItemReferenceError, WorkItemService
from test.support.database_safety import assert_isolated_database


def main() -> None:
    assert_isolated_database(engine, EXPECTED_DB)
    db = SessionLocal()
    created_ids: dict[str, int] = {}
    try:
        actor = db.query(User).filter(User.is_active.is_(True)).order_by(User.id).first()
        clients = db.query(Client).filter(Client.deleted_at.is_(None)).order_by(Client.id).limit(2).all()
        assert actor is not None and len(clients) == 2
        service = WorkItemService(db)
        payload = WorkItemCreate(
            item_type="realization",
            title="Synthetic realization linkage",
            description="Isolated transaction test",
            start_at=datetime.fromisoformat("2026-08-25T09:00:00+02:00"),
            due_at=datetime.fromisoformat("2026-08-28T17:00:00+02:00"),
            timezone_name="Europe/Warsaw",
            status="todo",
            client_id=clients[0].id,
        )
        item = service.create(payload, actor)
        created_ids["work_item"] = item.id
        assert item.project_id is not None
        created_ids["project"] = item.project_id
        project = db.query(Project).filter(Project.id == item.project_id).one()
        assert project.client_id == clients[0].id
        assert project.name == payload.title and project.status == "planned"
        assert str(project.start_date) == "2026-08-25" and str(project.end_date) == "2026-08-28"

        item = service.update(
            item.id,
            WorkItemUpdate(
                expected_version=item.version,
                title="Synthetic realization updated",
                status="in_progress",
                due_at=datetime.fromisoformat("2026-08-29T17:00:00+02:00"),
            ),
            actor,
        )
        project = db.query(Project).filter(Project.id == item.project_id).one()
        assert project.name == item.title and project.status == "active"
        assert str(project.end_date) == "2026-08-29"

        document = Document(
            filename="synthetic-owner-patch.txt",
            original_filename="synthetic-owner-patch.txt",
            content_type="text/plain",
            file_size=4,
            source_type="manual_upload",
        )
        db.add(document)
        db.commit()
        created_ids["document"] = document.id
        link = service.link_document(item.id, document.id, None, actor)
        created_ids["link"] = link.id
        db.refresh(document)
        assert document.client_id == item.client_id
        assert document.project_id == item.project_id
        assert db.query(WorkItemDocument).filter_by(document_id=document.id).count() == 1

        foreign = Document(
            filename="synthetic-foreign.txt",
            original_filename="synthetic-foreign.txt",
            content_type="text/plain",
            file_size=4,
            source_type="manual_upload",
            client_id=clients[1].id,
        )
        db.add(foreign)
        db.commit()
        created_ids["foreign"] = foreign.id
        try:
            service.link_document(item.id, foreign.id, None, actor)
            raise AssertionError("cross-client link unexpectedly accepted")
        except WorkItemReferenceError as error:
            assert str(error) == "cross_client_document"
            db.rollback()

        archived = service.set_archived(item.id, item.version, actor, archived=True)
        db.refresh(project)
        assert archived.deleted_at is not None and project.deleted_at is not None
        restored = service.set_archived(item.id, archived.version, actor, archived=False)
        db.refresh(project)
        assert restored.deleted_at is None and project.deleted_at is None
        all_day = service.create(WorkItemCreate(
            item_type="task",
            title="Synthetic all-day timezone range",
            start_at=datetime.fromisoformat("2026-08-24T22:00:00+00:00"),
            due_at=datetime.fromisoformat("2026-08-27T22:00:00+00:00"),
            all_day=True,
            timezone_name="Europe/Warsaw",
        ), actor)
        created_ids["all_day"] = all_day.id
        entry = next(row for row in CalendarService(db).month(2026, 8, actor).items if row.entity_id == all_day.id)
        assert str(entry.start) == "2026-08-25" and str(entry.end) == "2026-08-28"
        print("OWNER_CALENDAR_REALIZATION_PATCH 9/9 PASS")
    finally:
        db.rollback()
        if "work_item" in created_ids:
            db.query(WorkItemDocument).filter(WorkItemDocument.work_item_id == created_ids["work_item"]).delete(synchronize_session=False)
        for key in ("document", "foreign"):
            if key in created_ids:
                db.query(Document).filter(Document.id == created_ids[key]).delete(synchronize_session=False)
        if "work_item" in created_ids:
            db.query(WorkItem).filter(WorkItem.id == created_ids["work_item"]).delete(synchronize_session=False)
        if "all_day" in created_ids:
            db.query(WorkItem).filter(WorkItem.id == created_ids["all_day"]).delete(synchronize_session=False)
        if "project" in created_ids:
            db.query(Project).filter(Project.id == created_ids["project"]).delete(synchronize_session=False)
        db.commit()
        db.close()


if __name__ == "__main__":
    main()
