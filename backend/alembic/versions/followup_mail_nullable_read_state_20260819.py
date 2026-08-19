"""Correct nullable Gmail read state and replace its ordered index online.

Revision ID: followup_mail_nullable_read_state_20260819
Revises: followup_mail_read_index_supersession_20260819
"""

from alembic import op
import sqlalchemy as sa

from app.database.global_mail_sql import (
    GMAIL_MESSAGE_TIME_SQL,
    GMAIL_READ_STATE_SQL,
    GMAIL_SOURCE_PREDICATE_SQL,
)


revision = "followup_mail_nullable_read_state_20260819"
down_revision = "followup_mail_read_index_supersession_20260819"
branch_labels = None
depends_on = None


CORRECTED_INDEX = "ix_candidate_sources_gmail_read_state_v2_time"
PREVIOUS_INDEX = "ix_candidate_sources_gmail_read_time"

PREVIOUS_READ_STATE_SQL = """
CASE
  WHEN json_typeof(coalesce(raw_payload -> 'labelIds',
                            raw_payload -> 'labels')) <> 'array'
    THEN NULL
  WHEN upper(coalesce((raw_payload -> 'labelIds')::text,
                      (raw_payload -> 'labels')::text, '[]')) LIKE '%"UNREAD"%'
    THEN 'unread'
  ELSE 'read'
END
""".strip()


def _require_valid_index(name: str) -> None:
    row = op.get_bind().execute(
        sa.text(
            "SELECT i.indisvalid, i.indisready "
            "FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
            "WHERE c.relname = :name"
        ),
        {"name": name},
    ).one_or_none()
    if row is None or not row.indisvalid or not row.indisready:
        raise RuntimeError(f"index {name} is not valid and ready")


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY {CORRECTED_INDEX} "
            f"ON candidate_sources (({GMAIL_READ_STATE_SQL}), "
            f"({GMAIL_MESSAGE_TIME_SQL}) DESC, id DESC) "
            f"WHERE {GMAIL_SOURCE_PREDICATE_SQL}"
        )
    _require_valid_index(CORRECTED_INDEX)
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {PREVIOUS_INDEX}")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY {PREVIOUS_INDEX} "
            f"ON candidate_sources (({PREVIOUS_READ_STATE_SQL}), "
            f"({GMAIL_MESSAGE_TIME_SQL}) DESC, id DESC) "
            f"WHERE {GMAIL_SOURCE_PREDICATE_SQL}"
        )
    _require_valid_index(PREVIOUS_INDEX)
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {CORRECTED_INDEX}")
