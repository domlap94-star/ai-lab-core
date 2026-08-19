"""Supersede the legacy Gmail read-state index online.

Revision ID: followup_mail_read_index_supersession_20260819
Revises: followup_mail_composite_indexes_20260819
"""

from alembic import op


revision = "followup_mail_read_index_supersession_20260819"
down_revision = "followup_mail_composite_indexes_20260819"
branch_labels = None
depends_on = None


INDEX_NAME = "ix_candidate_sources_gmail_read_state"

READ_STATE_SQL = """
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

PREDICATE = "source_type = 'gmail_message' AND deleted_at IS NULL"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY {INDEX_NAME} "
            f"ON candidate_sources (({READ_STATE_SQL})) WHERE {PREDICATE}"
        )
