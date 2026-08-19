from datetime import datetime
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.global_mail_sql import (
    GMAIL_DIRECTION_SQL,
    GMAIL_MESSAGE_TIME_SQL,
    GMAIL_READ_STATE_SQL,
    GMAIL_SEARCH_DOCUMENT_SQL,
)
from app.models.document import Document


def _source_expression(value: str) -> str:
    """Qualify the canonical expression without changing its SQL semantics."""
    result = re.sub(r"\braw_payload\b", "cs.raw_payload", value)
    result = re.sub(r"\bextracted_text\b", "cs.extracted_text", result)
    return re.sub(r"\bcreated_at\b", "cs.created_at", result)


DIRECTION_SQL = _source_expression(GMAIL_DIRECTION_SQL)
READ_STATE_SQL = _source_expression(GMAIL_READ_STATE_SQL)
MESSAGE_TIME_SQL = _source_expression(GMAIL_MESSAGE_TIME_SQL)
SEARCH_DOCUMENT_SQL = _source_expression(GMAIL_SEARCH_DOCUMENT_SQL)


class GlobalMailRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _select_sql() -> str:
        return f"""
SELECT cs.id AS source_id, cs.external_id AS message_id,
       cs.external_parent_id AS thread_id, cs.raw_payload,
       cs.extracted_text, cs.created_at,
       ({DIRECTION_SQL}) AS direction,
       ({READ_STATE_SQL}) AS read_state,
       ({MESSAGE_TIME_SQL}) AS occurred_at,
       CASE WHEN cc.status IN ('accepted','merged','duplicate')
            THEN cc.matched_client_id END AS client_id,
       CASE WHEN cc.status IN ('accepted','merged','duplicate')
            THEN c.name END AS client_name,
       cc.status AS review_state,
       (SELECT count(*) FROM documents d
        WHERE d.source_type='gmail_attachment'
          AND d.gmail_message_id=cs.external_id) AS attachment_count
FROM candidate_sources cs
LEFT JOIN client_candidates cc
  ON cc.id=cs.candidate_id AND cc.deleted_at IS NULL
LEFT JOIN clients c ON c.id=cc.matched_client_id AND c.deleted_at IS NULL
"""

    def get_page(
        self,
        *,
        search: str | None,
        client_id: int | None,
        direction: str | None,
        linked: bool | None,
        has_attachments: bool | None,
        read_state: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        thread_id: str | None,
        skip: int,
        limit: int,
    ) -> tuple[list[Any], bool]:
        conditions = ["cs.source_type='gmail_message'", "cs.deleted_at IS NULL"]
        params: dict[str, Any] = {"skip": skip, "fetch": limit + 1}
        if search:
            conditions.append(
                f"({SEARCH_DOCUMENT_SQL}) @@ plainto_tsquery('simple', :search)"
            )
            params["search"] = search
        if client_id is not None:
            conditions.extend(
                [
                    "cc.matched_client_id=:client_id",
                    "cc.status IN ('accepted','merged','duplicate')",
                ]
            )
            params["client_id"] = client_id
        if direction:
            conditions.append(f"({DIRECTION_SQL})=:direction")
            params["direction"] = direction
        if linked is not None:
            expression = (
                "cc.matched_client_id IS NOT NULL AND "
                "cc.status IN ('accepted','merged','duplicate')"
            )
            conditions.append(f"({expression})" if linked else f"NOT ({expression})")
        if has_attachments is not None:
            expression = (
                "EXISTS (SELECT 1 FROM documents d "
                "WHERE d.source_type='gmail_attachment' "
                "AND d.gmail_message_id=cs.external_id)"
            )
            conditions.append(expression if has_attachments else f"NOT ({expression})")
        if read_state:
            if read_state == "unknown":
                conditions.append(f"({READ_STATE_SQL}) IS NULL")
            else:
                conditions.append(f"({READ_STATE_SQL})=:read_state")
                params["read_state"] = read_state
        if date_from is not None:
            conditions.append(f"({MESSAGE_TIME_SQL}) >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            conditions.append(f"({MESSAGE_TIME_SQL}) <= :date_to")
            params["date_to"] = date_to
        if thread_id:
            conditions.append("cs.external_parent_id=:thread_id")
            params["thread_id"] = thread_id

        # Including the constant read-state key makes PostgreSQL retain the
        # ordered V2 expression-index path instead of a broad bitmap + sort.
        order_prefix = f"({READ_STATE_SQL}), " if read_state else ""
        sql = (
            self._select_sql()
            + " WHERE "
            + " AND ".join(conditions)
            + f" ORDER BY {order_prefix}({MESSAGE_TIME_SQL}) DESC, cs.id DESC"
            + " OFFSET :skip LIMIT :fetch"
        )
        rows = list(self.db.execute(text(sql), params).mappings())
        return rows[:limit], len(rows) > limit

    def get_one(self, source_id: int) -> Any | None:
        sql = self._select_sql() + " WHERE cs.id=:source_id AND cs.source_type='gmail_message' AND cs.deleted_at IS NULL"
        return self.db.execute(text(sql), {"source_id": source_id}).mappings().one_or_none()

    def get_thread(self, thread_id: str, limit: int) -> list[Any]:
        sql = (
            self._select_sql()
            + " WHERE cs.source_type='gmail_message' AND cs.deleted_at IS NULL "
            + "AND cs.external_parent_id=:thread_id "
            + f"ORDER BY ({MESSAGE_TIME_SQL}) ASC, cs.id ASC LIMIT :limit"
        )
        return list(self.db.execute(text(sql), {"thread_id": thread_id, "limit": limit}).mappings())

    def get_attachments(self, message_ids: list[str]) -> list[Document]:
        if not message_ids:
            return []
        return (
            self.db.query(Document)
            .filter(
                Document.source_type == "gmail_attachment",
                Document.gmail_message_id.in_(message_ids),
            )
            .order_by(Document.gmail_message_id.asc(), Document.id.asc())
            .all()
        )

    def get_documents_by_ids(self, document_ids: list[int]) -> list[Document]:
        if not document_ids:
            return []
        return self.db.query(Document).filter(Document.id.in_(document_ids)).order_by(Document.id).all()
