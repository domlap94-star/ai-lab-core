"""add industries and clients

Revision ID: 7f3c2d9a8b10
Revises: dd90639e2a5b
Create Date: 2026-07-29 15:30:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f3c2d9a8b10"
down_revision: Union[str, Sequence[str], None] = "dd90639e2a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "industries",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "code",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "code",
            name="uq_industries_code",
        ),
        sa.UniqueConstraint(
            "name",
            name="uq_industries_name",
        ),
    )

    op.create_index(
        "ix_industries_code",
        "industries",
        ["code"],
        unique=True,
    )

    op.create_index(
        "ix_industries_name",
        "industries",
        ["name"],
        unique=True,
    )

    op.create_table(
        "clients",
        sa.Column(
            "client_type",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "legal_name",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "tax_id",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column(
            "registration_number",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "industry_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "website",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "primary_email",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "primary_phone",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "street",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "building_number",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "unit_number",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "postal_code",
            sa.String(length=20),
            nullable=True,
        ),
        sa.Column(
            "city",
            sa.String(length=150),
            nullable=True,
        ),
        sa.Column(
            "country_code",
            sa.String(length=2),
            server_default=sa.text("'PL'"),
            nullable=False,
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "client_type IN "
            "('company', 'person', 'institution', 'other')",
            name="ck_clients_client_type",
        ),
        sa.CheckConstraint(
            "char_length(country_code) = 2",
            name="ck_clients_country_code_length",
        ),
        sa.CheckConstraint(
            "char_length(trim(name)) > 0",
            name="ck_clients_name_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["industry_id"],
            ["industries.id"],
            name="fk_clients_industry_id_industries",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_clients_name",
        "clients",
        ["name"],
        unique=False,
    )

    op.create_index(
        "ix_clients_tax_id",
        "clients",
        ["tax_id"],
        unique=False,
    )

    op.create_index(
        "ix_clients_primary_email",
        "clients",
        ["primary_email"],
        unique=False,
    )

    op.create_index(
        "ix_clients_city",
        "clients",
        ["city"],
        unique=False,
    )

    op.create_index(
        "ix_clients_deleted_at",
        "clients",
        ["deleted_at"],
        unique=False,
    )

    op.create_index(
        "ix_clients_industry_id",
        "clients",
        ["industry_id"],
        unique=False,
    )

    industries_table = sa.table(
        "industries",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_active", sa.Boolean()),
    )

    op.bulk_insert(
        industries_table,
        [
            {
                "code": "food",
                "name": "Food",
                "description": "Food production and processing",
                "is_active": True,
            },
            {
                "code": "logistics",
                "name": "Logistics",
                "description": "Logistics and warehousing",
                "is_active": True,
            },
            {
                "code": "manufacturing",
                "name": "Manufacturing",
                "description": "Industrial manufacturing",
                "is_active": True,
            },
            {
                "code": "construction",
                "name": "Construction",
                "description": "Construction industry",
                "is_active": True,
            },
            {
                "code": "retail",
                "name": "Retail",
                "description": "Retail and commercial facilities",
                "is_active": True,
            },
            {
                "code": "public_sector",
                "name": "Public sector",
                "description": "Public administration and institutions",
                "is_active": True,
            },
            {
                "code": "residential",
                "name": "Residential",
                "description": "Residential buildings and private clients",
                "is_active": True,
            },
            {
                "code": "agriculture",
                "name": "Agriculture",
                "description": "Agriculture and agricultural facilities",
                "is_active": True,
            },
            {
                "code": "automotive",
                "name": "Automotive",
                "description": "Automotive industry",
                "is_active": True,
            },
            {
                "code": "other",
                "name": "Other",
                "description": "Other industries",
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_clients_industry_id",
        table_name="clients",
    )

    op.drop_index(
        "ix_clients_deleted_at",
        table_name="clients",
    )

    op.drop_index(
        "ix_clients_city",
        table_name="clients",
    )

    op.drop_index(
        "ix_clients_primary_email",
        table_name="clients",
    )

    op.drop_index(
        "ix_clients_tax_id",
        table_name="clients",
    )

    op.drop_index(
        "ix_clients_name",
        table_name="clients",
    )

    op.drop_table("clients")

    op.drop_index(
        "ix_industries_name",
        table_name="industries",
    )

    op.drop_index(
        "ix_industries_code",
        table_name="industries",
    )

    op.drop_table("industries")