"""Add the bounded Candidate merge audit trail.

Revision ID: followup_candidate_merge_audit_20260819
Revises: followup_clientdate_20260819
"""

from alembic import op
import sqlalchemy as sa


revision = "followup_candidate_merge_audit_20260819"
down_revision = "followup_clientdate_20260819"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The approved revision identifier is longer than the legacy Alembic
    # VARCHAR(32). This changes migration metadata capacity only; no business
    # row or application table is rewritten.
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.create_table(
        "candidate_merge_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column("target_client_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("relation_counts", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action = 'candidate_merged'",
            name="ck_candidate_merge_events_action",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["client_candidates.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_client_id"], ["clients.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_id", name="uq_candidate_merge_events_operation_id"),
    )
    op.create_index(
        "ix_candidate_merge_events_candidate_created",
        "candidate_merge_events",
        ["candidate_id", "created_at"],
    )
    op.create_index(
        "ix_candidate_merge_events_target_created",
        "candidate_merge_events",
        ["target_client_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_merge_events_target_created",
        table_name="candidate_merge_events",
    )
    op.drop_index(
        "ix_candidate_merge_events_candidate_created",
        table_name="candidate_merge_events",
    )
    op.drop_table("candidate_merge_events")
    # Keep alembic_version at VARCHAR(64): Alembic updates the revision value
    # only after this function returns, so narrowing while the 39-character
    # revision is still stored would make downgrade fail.
