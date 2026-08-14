"""add user management fields and standard user role

Revision ID: authv1_20260813
Revises: 98987aa23248
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "authv1_20260813"
down_revision: Union[str, Sequence[str], None] = "98987aa23248"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "password_reset_requested",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )

    op.execute(
        """
        INSERT INTO roles (name, description)
        SELECT 'User', 'Standard system user'
        WHERE NOT EXISTS (
            SELECT 1
            FROM roles
            WHERE name = 'User'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM roles
        WHERE name = 'User'
          AND NOT EXISTS (
              SELECT 1
              FROM users
              WHERE users.role_id = roles.id
          )
        """
    )

    op.drop_column(
        "users",
        "password_reset_requested",
    )

    op.drop_column(
        "users",
        "must_change_password",
    )
