from sqlalchemy.orm import Session

from app.models.industry import Industry
from app.repositories.base_repository import BaseRepository


class IndustryRepository(BaseRepository[Industry]):
    def __init__(self, db: Session) -> None:
        super().__init__(db, Industry)

    def get_active(self, industry_id: int) -> Industry | None:
        return (
            self.db.query(Industry)
            .filter(
                Industry.id == industry_id,
                Industry.is_active.is_(True),
            )
            .first()
        )

    def get_all_active(self) -> list[Industry]:
        return (
            self.db.query(Industry)
            .filter(Industry.is_active.is_(True))
            .order_by(Industry.name.asc())
            .all()
        )

    def get_by_code(self, code: str) -> Industry | None:
        return (
            self.db.query(Industry)
            .filter(Industry.code == code)
            .first()
        )