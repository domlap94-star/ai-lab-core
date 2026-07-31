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