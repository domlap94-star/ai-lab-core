"""Add the bounded Gmail lexical search index for CHUNK 11.

Revision ID: chunk11search_20260818
Revises: prechunk11status_20260817
Create Date: 2026-08-18
"""

from alembic import op


revision = "chunk11search_20260818"
down_revision = "prechunk11status_20260817"
branch_labels = None
depends_on = None


EMAIL_SEARCH_DOCUMENT = """
to_tsvector(
    'simple',
    coalesce(raw_payload ->> 'subject', '') || ' ' ||
    coalesce(raw_payload ->> 'Subject', '') || ' ' ||
    coalesce(raw_payload ->> 'from', '') || ' ' ||
    coalesce(raw_payload ->> 'From', '') || ' ' ||
    coalesce(raw_payload ->> 'to', '') || ' ' ||
    coalesce(raw_payload ->> 'To', '') || ' ' ||
    coalesce(raw_payload ->> 'text', '') || ' ' ||
    coalesce(raw_payload ->> 'textPlain', '') || ' ' ||
    coalesce(raw_payload ->> 'snippet', '') || ' ' ||
    coalesce(extracted_text, '')
)
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE INDEX ix_candidate_sources_gmail_search_vector
        ON candidate_sources
        USING gin (({EMAIL_SEARCH_DOCUMENT}))
        WHERE source_type = 'gmail_message' AND deleted_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_candidate_sources_gmail_search_vector"
    )
