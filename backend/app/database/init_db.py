from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.database.seed_admin import seed_admin


def init_database() -> None:
    """
    Initializes application data after Alembic migrations have been applied.

    Database tables are managed exclusively by Alembic.
    """

    db: Session = SessionLocal()

    try:
        seed_admin(db)
    finally:
        db.close()


def verify_database_ready_read_only(
    *,
    expected_schema_revision: str | None,
    expected_admin_username: str,
) -> None:
    """Fail closed unless an existing database is ready without bootstrap writes."""

    if not expected_schema_revision:
        raise RuntimeError("database_schema_revision_required")

    db: Session = SessionLocal()
    try:
        # PostgreSQL enforces this transaction as read-only. The transaction is
        # always rolled back below; no ORM mutation helpers are used here.
        db.execute(text("SET TRANSACTION READ ONLY"))
        db.execute(text("SET LOCAL statement_timeout = '5000ms'"))

        observed_revision = db.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
        if observed_revision != expected_schema_revision:
            raise RuntimeError("database_schema_revision_mismatch")

        administrator_role = db.execute(
            text(
                "SELECT id FROM roles "
                "WHERE name = :role_name "
                "LIMIT 1"
            ),
            {"role_name": "Administrator"},
        ).scalar_one_or_none()
        if administrator_role is None:
            raise RuntimeError("database_administrator_role_missing")

        administrator = db.execute(
            text(
                "SELECT 1 FROM users "
                "WHERE username = :username "
                "AND role_id = :role_id "
                "AND is_active IS TRUE "
                "AND trashed_at IS NULL "
                "LIMIT 1"
            ),
            {
                "username": expected_admin_username,
                "role_id": administrator_role,
            },
        ).scalar_one_or_none()
        if administrator is None:
            raise RuntimeError("database_administrator_user_missing")
    except RuntimeError:
        raise
    except SQLAlchemyError as exc:
        raise RuntimeError("database_readiness_check_failed") from exc
    finally:
        db.rollback()
        db.close()
