"""Add reversible document-client link audit events.

Revision ID: chunk8doclink_20260817
Revises: chunk7addr_20260816
"""

from alembic import op
import sqlalchemy as sa


revision = "chunk8doclink_20260817"
down_revision = "chunk7addr_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_client_link_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("old_client_id", sa.BigInteger(), nullable=True),
        sa.Column("new_client_id", sa.BigInteger(), nullable=True),
        sa.Column("previous_candidate_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=False, server_default="manual"),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=True),
        sa.Column("reversal_of_event_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("action IN ('LINK', 'UNLINK', 'MOVE')", name="ck_document_client_link_events_action"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["old_client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["new_client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["previous_candidate_id"], ["client_candidates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversal_of_event_id"], ["document_client_link_events.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reversal_of_event_id"),
    )
    op.create_index(
        "ix_document_client_link_events_document",
        "document_client_link_events",
        ["document_id", "created_at"],
    )
    op.create_index(
        "ix_document_client_link_events_actor",
        "document_client_link_events",
        ["actor_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_client_link_events_actor", table_name="document_client_link_events")
    op.drop_index("ix_document_client_link_events_document", table_name="document_client_link_events")
    op.drop_table("document_client_link_events")
