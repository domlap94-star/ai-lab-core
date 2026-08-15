from datetime import date, datetime
import re

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate


SOURCE_DATE_KEY = "DATA"
SOURCE_DATE_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
LINKED_CANDIDATE_STATUSES = ("accepted", "merged", "duplicate")


class ClientSourceRecordDateService:
    """Read-only projection of the earliest valid Sheets record date."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @classmethod
    def parse_payload(cls, payload: object) -> date | None:
        if not isinstance(payload, dict):
            return None

        values = [
            value.strip()
            for key, value in payload.items()
            if cls._normalize_key(key) == SOURCE_DATE_KEY
            and isinstance(value, str)
            and value.strip()
        ]

        parsed_values = [
            parsed
            for value in values
            if (parsed := cls.parse_value(value)) is not None
        ]

        return min(parsed_values) if parsed_values else None

    @staticmethod
    def parse_value(value: str) -> date | None:
        normalized = value.strip()

        if not SOURCE_DATE_PATTERN.fullmatch(normalized):
            return None

        try:
            return datetime.strptime(normalized, "%d.%m.%Y").date()
        except ValueError:
            return None

    def get_for_client_ids(self, client_ids: list[int]) -> dict[int, date]:
        unique_ids = sorted(set(client_ids))
        if not unique_ids:
            return {}

        rows = (
            self.db.query(
                ClientCandidate.matched_client_id,
                CandidateSource.raw_payload,
            )
            .join(
                CandidateSource,
                CandidateSource.candidate_id == ClientCandidate.id,
            )
            .filter(
                ClientCandidate.matched_client_id.in_(unique_ids),
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.status.in_(LINKED_CANDIDATE_STATUSES),
                CandidateSource.deleted_at.is_(None),
                CandidateSource.source_type == "google_sheets_row",
            )
            .all()
        )

        result: dict[int, date] = {}
        for client_id, payload in rows:
            if client_id is None:
                continue

            parsed = self.parse_payload(payload)
            if parsed is None:
                continue

            current = result.get(client_id)
            if current is None or parsed < current:
                result[client_id] = parsed

        return result

    @staticmethod
    def effective_created_date(
        created_at: datetime,
        source_record_date: date | None,
    ) -> date:
        return source_record_date or created_at.date()

    @classmethod
    def order_client_ids(
        cls,
        candidates: list[tuple[int, datetime]],
        source_dates: dict[int, date],
        *,
        sort_order: str,
    ) -> list[int]:
        reverse = sort_order == "newest"

        ordered = sorted(
            candidates,
            key=lambda row: (
                cls.effective_created_date(
                    row[1],
                    source_dates.get(row[0]),
                ),
                row[0],
            ),
            reverse=reverse,
        )

        return [client_id for client_id, _ in ordered]

    @staticmethod
    def _normalize_key(value: object) -> str:
        if not isinstance(value, str):
            return ""

        return " ".join(value.strip().upper().split())
