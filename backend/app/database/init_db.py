from sqlalchemy.orm import Session

import app.models
from app.database.base import Base
from app.database.engine import engine
from app.database.session import SessionLocal
from app.database.seed_admin import seed_admin


def init_database() -> None:
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()

    try:
        seed_admin(db)
    finally:
        db.close()