"""Add query-only indexes for the global Gmail workspace.

Revision ID: followup_mail_query_indexes_20260819
Revises: followup_change_history_20260819
"""

from alembic import op


revision = "followup_mail_query_indexes_20260819"
down_revision = "followup_change_history_20260819"
branch_labels = None
depends_on = None


DIRECTION_SQL = """
CASE
  WHEN lower(coalesce(raw_payload ->> 'direction', ''))
       IN ('sent', 'outgoing', 'wyslana', 'wysłana')
    OR upper(coalesce((raw_payload -> 'labelIds')::text,
                      (raw_payload -> 'labels')::text, '[]')) LIKE '%"SENT"%'
    THEN 'sent'
  WHEN lower(coalesce(raw_payload ->> 'direction', ''))
       IN ('received', 'incoming', 'odebrana')
    OR upper(coalesce((raw_payload -> 'labelIds')::text,
                      (raw_payload -> 'labels')::text, '[]')) LIKE '%"INBOX"%'
    THEN 'received'
  ELSE 'unknown'
END
""".strip()

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

MESSAGE_TIME_SQL = """
CASE
  WHEN json_typeof(raw_payload -> 'date') = 'string'
   AND raw_payload ->> 'date' ~
       '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{3}Z$'
    THEN make_timestamp(
      substring(raw_payload ->> 'date', 1, 4)::integer,
      substring(raw_payload ->> 'date', 6, 2)::integer,
      substring(raw_payload ->> 'date', 9, 2)::integer,
      substring(raw_payload ->> 'date', 12, 2)::integer,
      substring(raw_payload ->> 'date', 15, 2)::integer,
      substring(raw_payload ->> 'date', 18, 6)::double precision
    )
  WHEN json_typeof(raw_payload -> 'internalDate') = 'string'
   AND raw_payload ->> 'internalDate' ~ '^[0-9]{13}$'
    THEN timestamp 'epoch'
       + ((raw_payload ->> 'internalDate')::double precision / 1000.0)
         * interval '1 second'
  ELSE created_at AT TIME ZONE 'UTC'
END
""".strip()

PREDICATE = "source_type = 'gmail_message' AND deleted_at IS NULL"


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_candidate_sources_gmail_direction "
        f"ON candidate_sources (({DIRECTION_SQL})) WHERE {PREDICATE}"
    )
    op.execute(
        "CREATE INDEX ix_candidate_sources_gmail_read_state "
        f"ON candidate_sources (({READ_STATE_SQL})) WHERE {PREDICATE}"
    )
    op.execute(
        "CREATE INDEX ix_candidate_sources_gmail_message_time "
        f"ON candidate_sources (({MESSAGE_TIME_SQL}) DESC, id DESC) "
        f"WHERE {PREDICATE}"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_candidate_sources_gmail_message_time")
    op.execute("DROP INDEX IF EXISTS ix_candidate_sources_gmail_read_state")
    op.execute("DROP INDEX IF EXISTS ix_candidate_sources_gmail_direction")
