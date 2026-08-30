from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import DateTime, Numeric, and_, case, cast, func, literal_column, or_
from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.models.ignored_mail_source import IgnoredMailSource
from app.database.global_mail_sql import GMAIL_SENDER_EMAIL_SQL


LINKED_CANDIDATE_STATUSES = (
    "accepted",
    "merged",
    "duplicate",
)


class ClientEmailRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _message_at_expression():
        date_text = CandidateSource.raw_payload.op("->>")("date")
        internal_date_text = CandidateSource.raw_payload.op("->>")(
            "internalDate"
        )

        return case(
            (
                date_text.op("~")(
                    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
                ),
                cast(date_text, DateTime(timezone=True)),
            ),
            (
                internal_date_text.op("~")(r"^\d{10,16}$"),
                func.to_timestamp(
                    cast(internal_date_text, Numeric) / 1000
                ),
            ),
            else_=None,
        )

    def _deduplicated_sources(self, client_id: int):
        message_at = self._message_at_expression()
        sender_email = literal_column(
            "(" + GMAIL_SENDER_EMAIL_SQL.replace(
                "raw_payload", "candidate_sources.raw_payload"
            ) + ")"
        )
        row_number = func.row_number().over(
            partition_by=(
                CandidateSource.import_source_id,
                CandidateSource.external_id,
            ),
            order_by=(
                message_at.desc().nulls_last(),
                CandidateSource.id.desc(),
            ),
        )

        return (
            self.db.query(
                CandidateSource.id.label("source_id"),
                CandidateSource.external_id,
                CandidateSource.external_parent_id,
                CandidateSource.source_url,
                CandidateSource.extracted_text,
                CandidateSource.raw_payload,
                CandidateSource.created_at,
                ClientCandidate.primary_email,
                sender_email.label("sender_email"),
                self.db.query(IgnoredMailSource.id).filter(
                    IgnoredMailSource.is_active.is_(True),
                    or_(
                        and_(
                            IgnoredMailSource.rule_type == "email",
                            IgnoredMailSource.normalized_value
                            == sender_email,
                        ),
                        and_(
                            IgnoredMailSource.rule_type == "domain",
                            IgnoredMailSource.normalized_value
                            == func.split_part(
                                sender_email,
                                "@",
                                2,
                            ),
                        ),
                    ),
                ).exists().label("ignored"),
                message_at.label("message_at"),
                row_number.label("duplicate_rank"),
            )
            .join(
                ClientCandidate,
                ClientCandidate.id == CandidateSource.candidate_id,
            )
            .filter(
                CandidateSource.source_type == "gmail_message",
                CandidateSource.deleted_at.is_(None),
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.matched_client_id == client_id,
                ClientCandidate.status.in_(LINKED_CANDIDATE_STATUSES),
            )
            .subquery()
        )

    def get_page(
        self,
        *,
        client_id: int,
        skip: int,
        limit: int,
        source_id: int | None = None,
        ignored: bool | None = None,
    ) -> tuple[Sequence[object], int]:
        sources = self._deduplicated_sources(client_id)
        filtered = self.db.query(sources).filter(
            sources.c.duplicate_rank == 1
        )
        if source_id is not None:
            filtered = filtered.filter(sources.c.source_id == source_id)
        if ignored is not None:
            filtered = filtered.filter(sources.c.ignored.is_(ignored))

        total = filtered.count()
        items = (
            filtered.order_by(
                sources.c.message_at.desc().nulls_last(),
                sources.c.source_id.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total

    def get_attachments(
        self,
        client_id: int,
        message_ids: Sequence[str],
    ) -> list[Document]:
        if not message_ids:
            return []

        return (
            self.db.query(Document)
            .outerjoin(
                ClientCandidate,
                ClientCandidate.id == Document.candidate_id,
            )
            .filter(
                Document.source_type == "gmail_attachment",
                Document.gmail_message_id.in_(message_ids),
                Document.trashed_at.is_(None),
                Document.purged_at.is_(None),
                or_(
                    Document.client_id == client_id,
                    and_(
                        Document.client_id.is_(None),
                        ClientCandidate.id.isnot(None),
                        ClientCandidate.deleted_at.is_(None),
                        ClientCandidate.matched_client_id == client_id,
                        ClientCandidate.status.in_(
                            LINKED_CANDIDATE_STATUSES
                        ),
                    ),
                ),
            )
            .order_by(
                Document.gmail_message_id.asc(),
                Document.id.asc(),
            )
            .all()
        )
