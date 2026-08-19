"""Read-only evidence for the FOLLOW-UP CHUNK 06 activity design gate.

The script prints aggregate counts and bounded timeline characteristics only.
It never emits Client names, contact values, email subjects or message bodies.
"""

from collections import Counter
from time import perf_counter

from sqlalchemy import func, text

from app.database.session import SessionLocal
from app.models.agent_execution import AgentExecution
from app.models.candidate_merge_event import CandidateMergeEvent
from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.client_workflow_status import ClientWorkflowStatus
from app.models.document import Document
from app.models.document_client_link_event import DocumentClientLinkEvent
from app.models.inspection import Inspection
from app.models.user_lifecycle_event import UserLifecycleEvent
from app.services.timeline_service import TimelineService


def main() -> None:
    db = SessionLocal()
    try:
        counts = {
            "clients": db.query(Client).count(),
            "documents": db.query(Document).count(),
            "inspections": db.query(Inspection).count(),
            "workflow_status_rows": db.query(ClientWorkflowStatus).count(),
            "candidate_merge_events": db.query(CandidateMergeEvent).count(),
            "document_link_events": db.query(DocumentClientLinkEvent).count(),
            "user_lifecycle_events": db.query(UserLifecycleEvent).count(),
            "agent_executions": db.query(AgentExecution).count(),
            "gmail_sources": db.query(CandidateSource)
            .filter(CandidateSource.source_type == "gmail_message")
            .count(),
        }
        for key, value in counts.items():
            print(f"{key}={value}")

        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        activity_table = db.execute(
            text("SELECT to_regclass('public.client_activity_events')")
        ).scalar_one_or_none()
        locks = db.execute(
            text("SELECT count(1) FROM pg_locks WHERE NOT granted")
        ).scalar_one()
        print(f"db_revision={revision}")
        print(f"client_activity_events_exists={activity_table is not None}")
        print(f"ungranted_locks={locks}")

        representative = (
            db.query(
                ClientCandidate.matched_client_id,
                func.count(CandidateSource.id).label("source_count"),
            )
            .join(CandidateSource, CandidateSource.candidate_id == ClientCandidate.id)
            .filter(
                CandidateSource.source_type == "gmail_message",
                CandidateSource.deleted_at.is_(None),
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.matched_client_id.is_not(None),
            )
            .group_by(ClientCandidate.matched_client_id)
            .order_by(func.count(CandidateSource.id).desc())
            .first()
        )
        if representative is not None:
            started = perf_counter()
            page = TimelineService(db).get_client_timeline(
                client_id=representative.matched_client_id,
                skip=0,
                limit=20,
            )
            duration_ms = (perf_counter() - started) * 1000
            event_types = Counter(item.event_type for item in page.items)
            stable_keys = [item.stable_key for item in page.items]
            forbidden_metadata = {"body", "body_text", "text", "raw_payload"}
            print(f"representative_email_sources={representative.source_count}")
            print(f"timeline_total={page.total}")
            print(f"timeline_returned={len(page.items)}")
            print(f"timeline_event_types={dict(sorted(event_types.items()))}")
            print(f"timeline_duplicate_stable_keys={len(stable_keys) - len(set(stable_keys))}")
            print(
                "timeline_forbidden_metadata_keys="
                + str(
                    sum(
                        bool(forbidden_metadata.intersection(item.metadata))
                        for item in page.items
                    )
                )
            )
            print(f"timeline_query_ms={duration_ms:.3f}")
        print("production_writes=0")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
