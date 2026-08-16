"""Add provenance-aware client addresses and contact provenance.

Revision ID: chunk7addr_20260816
Revises: contact_20260816
"""

from alembic import op
import sqlalchemy as sa


revision = "chunk7addr_20260816"
down_revision = "contact_20260816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_contact_points",
        sa.Column("origin", sa.String(20), nullable=False, server_default="migration"),
    )
    op.add_column(
        "client_contact_points", sa.Column("source_type", sa.String(50), nullable=True)
    )
    op.add_column(
        "client_contact_points", sa.Column("source_id", sa.BigInteger(), nullable=True)
    )
    op.create_foreign_key(
        "fk_client_contact_points_source_id",
        "client_contact_points",
        "candidate_sources",
        ["source_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_client_contact_points_source_id", "client_contact_points", ["source_id"]
    )
    op.create_check_constraint(
        "ck_client_contact_points_origin",
        "client_contact_points",
        "origin IN ('manual', 'gmail', 'sheets', 'migration', 'other')",
    )
    op.alter_column(
        "client_contact_points", "origin", server_default="manual"
    )

    op.create_table(
        "client_addresses",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(100), nullable=False, server_default="Adres"),
        sa.Column("street", sa.String(255), nullable=True),
        sa.Column("building_number", sa.String(50), nullable=True),
        sa.Column("unit_number", sa.String(50), nullable=True),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("city", sa.String(150), nullable=True),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="PL"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("origin", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("source_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("char_length(country_code) = 2", name="ck_client_addresses_country_code"),
        sa.CheckConstraint(
            "origin IN ('manual', 'gmail', 'sheets', 'migration', 'other')",
            name="ck_client_addresses_origin",
        ),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["candidate_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_addresses_client", "client_addresses", ["client_id"])
    op.create_index("ix_client_addresses_source", "client_addresses", ["source_id"])

    # Direct field-for-field compatibility projection only. No parsing,
    # geocoding, splitting or cleanup is performed.
    op.execute(
        """
        INSERT INTO client_addresses
            (client_id, label, street, building_number, unit_number,
             postal_code, city, country_code, is_primary, position,
             origin, source_type)
        SELECT id, 'Adres główny', street, building_number, unit_number,
               postal_code, city, country_code, true, 0,
               'migration', 'legacy_client_scalar'
        FROM clients
        WHERE NULLIF(trim(street), '') IS NOT NULL
           OR NULLIF(trim(building_number), '') IS NOT NULL
           OR NULLIF(trim(unit_number), '') IS NOT NULL
           OR NULLIF(trim(postal_code), '') IS NOT NULL
           OR NULLIF(trim(city), '') IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_client_addresses_source", table_name="client_addresses")
    op.drop_index("ix_client_addresses_client", table_name="client_addresses")
    op.drop_table("client_addresses")
    op.drop_constraint(
        "ck_client_contact_points_origin", "client_contact_points", type_="check"
    )
    op.drop_index("ix_client_contact_points_source_id", table_name="client_contact_points")
    op.drop_constraint(
        "fk_client_contact_points_source_id", "client_contact_points", type_="foreignkey"
    )
    op.drop_column("client_contact_points", "source_id")
    op.drop_column("client_contact_points", "source_type")
    op.drop_column("client_contact_points", "origin")
