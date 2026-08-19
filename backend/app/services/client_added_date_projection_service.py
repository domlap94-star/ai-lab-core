from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.client import Client
from app.services.client_source_record_date_service import (
    ClientSourceRecordDateService,
)


class ClientAddedDateProjectionService:
    """Canonical projection for the operator-facing Client added date."""

    def __init__(self, db: Session) -> None:
        self.source_dates = ClientSourceRecordDateService(db)

    @staticmethod
    def effective_date(
        *,
        created_at: datetime,
        source_record_date: date | None,
        client_added_at: date | None,
    ) -> date:
        return client_added_at or source_record_date or created_at.date()

    def source_dates_for(self, client_ids: list[int]) -> dict[int, date]:
        return self.source_dates.get_for_client_ids(client_ids)

    def attach(
        self,
        clients: list[Client],
        *,
        source_dates: dict[int, date] | None = None,
    ) -> None:
        dates = source_dates
        if dates is None:
            dates = self.source_dates_for([client.id for client in clients])

        for client in clients:
            source_date = dates.get(client.id)
            client.source_record_date = source_date
            client.effective_added_date = self.effective_date(
                created_at=client.created_at,
                source_record_date=source_date,
                client_added_at=client.client_added_at,
            )

    @classmethod
    def order_client_ids(
        cls,
        candidates: list[tuple[int, datetime, date | None]],
        source_dates: dict[int, date],
        *,
        sort_order: str,
    ) -> list[int]:
        reverse = sort_order == "newest"
        ordered = sorted(
            candidates,
            key=lambda row: (
                cls.effective_date(
                    created_at=row[1],
                    source_record_date=source_dates.get(row[0]),
                    client_added_at=row[2],
                ),
                row[0],
            ),
            reverse=reverse,
        )
        return [client_id for client_id, _, _ in ordered]
