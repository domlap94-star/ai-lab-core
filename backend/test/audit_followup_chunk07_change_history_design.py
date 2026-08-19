"""Read-only evidence for the FOLLOW-UP CHUNK 07 schema design gate.

The script prints only schema/table names, aggregate counts and boolean
write-surface characteristics. It never emits customer or user values.
"""

from sqlalchemy import inspect, text

from app.database.session import SessionLocal
from app.models.agent_execution import AgentExecution
from app.models.candidate_merge_event import CandidateMergeEvent
from app.models.client_activity_event import ClientActivityEvent
from app.models.document_client_link_event import DocumentClientLinkEvent
from app.models.user_lifecycle_event import UserLifecycleEvent


AUDIT_MODELS = {
    "candidate_merge_events": CandidateMergeEvent,
    "client_activity_events": ClientActivityEvent,
    "document_client_link_events": DocumentClientLinkEvent,
    "user_lifecycle_events": UserLifecycleEvent,
    "agent_executions": AgentExecution,
}


def main() -> None:
    db = SessionLocal()
    try:
        schema = inspect(db.bind)
        audit_like = sorted(
            table
            for table in schema.get_table_names()
            if any(
                token in table
                for token in ("event", "audit", "history", "log", "execution")
            )
        )
        print("audit_like_tables=" + ",".join(audit_like))
        for table, model in AUDIT_MODELS.items():
            print(f"{table}={db.query(model).count()}")

        print(
            "change_history_events_exists="
            + str(schema.has_table("change_history_events"))
        )
        revision = db.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        locks = db.execute(
            text("SELECT count(1) FROM pg_locks WHERE NOT granted")
        ).scalar_one()
        print(f"db_revision={revision}")
        print(f"ungranted_locks={locks}")

        # Model-level evidence that the current stores are domain-specific and
        # do not provide a generic entity/action/before/after contract.
        required_generic = {
            "entity_type",
            "entity_id",
            "action",
            "changed_fields",
            "before_values",
            "after_values",
        }
        for table, model in AUDIT_MODELS.items():
            columns = {column.name for column in model.__table__.columns}
            print(
                f"{table}_generic_contract="
                + str(required_generic.issubset(columns))
            )
        print("production_writes=0")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
