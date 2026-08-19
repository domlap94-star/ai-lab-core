from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.repositories.candidate_context_repository import (
    CandidateContextRepository,
)
from app.services.email_client_matching_service import EMAIL_MATCH_METADATA_KEY


class CandidateContextNotFoundError(Exception):
    pass


class CandidateContextService:
    def __init__(self, db: Session) -> None:
        self.repository = CandidateContextRepository(db)

    def build_context(
        self,
        candidate_id: int,
    ) -> dict[str, Any]:
        candidate = self.repository.get_candidate(candidate_id)

        if candidate is None:
            raise CandidateContextNotFoundError(
                f"Candidate {candidate_id} not found."
            )

        sources = self.repository.get_sources(candidate_id)
        documents = self.repository.get_documents(candidate_id)

        gmail_messages: list[dict[str, Any]] = []
        sheets_rows: list[dict[str, Any]] = []
        other_sources: list[dict[str, Any]] = []

        for source in sources:
            if source.source_type == "gmail_message":
                gmail_messages.append(
                    self._normalize_gmail_source(source)
                )

            elif source.source_type == "google_sheets_row":
                sheets_rows.append(
                    self._normalize_sheets_source(source)
                )

            else:
                other_sources.append(
                    self._normalize_generic_source(source)
                )

        normalized_documents = [
            self._normalize_document(document)
            for document in documents
        ]

        return {
            "candidate": {
                "id": candidate.id,
                "client_type": candidate.client_type,
                "name": candidate.name,
                "legal_name": candidate.legal_name,
                "tax_id": candidate.tax_id,
                "registration_number": candidate.registration_number,
                "website": candidate.website,
                "primary_email": candidate.primary_email,
                "primary_phone": candidate.primary_phone,
                "street": candidate.street,
                "building_number": candidate.building_number,
                "unit_number": candidate.unit_number,
                "postal_code": candidate.postal_code,
                "city": candidate.city,
                "country_code": candidate.country_code,
                "notes": candidate.notes,
                "status": candidate.status,
                "confidence": candidate.confidence,
                "matched_client_id": candidate.matched_client_id,
                "source_summary": candidate.source_summary,
                "created_at": self._serialize_datetime(
                    candidate.created_at
                ),
                "updated_at": self._serialize_datetime(
                    candidate.updated_at
                ),
            },
            "gmail_messages": gmail_messages,
            "sheets_rows": sheets_rows,
            "documents": normalized_documents,
            "other_sources": other_sources,
            "metadata": {
                "gmail_message_count": len(gmail_messages),
                "sheets_row_count": len(sheets_rows),
                "document_count": len(normalized_documents),
                "other_source_count": len(other_sources),
                "source_count": len(sources),
            },
        }

    def build_unmatched_documents_context(
        self,
    ) -> list[dict[str, Any]]:
        documents = self.repository.get_unmatched_documents()

        return [
            self._normalize_document(document)
            for document in documents
        ]

    def _normalize_gmail_source(
        self,
        source: Any,
    ) -> dict[str, Any]:
        payload = source.raw_payload or {}
        matching = payload.get(EMAIL_MATCH_METADATA_KEY)

        from_value = self._extract_mail_address(
            payload.get("from")
        )

        to_values = self._extract_mail_addresses(
            payload.get("to")
        )

        cc_values = self._extract_mail_addresses(
            payload.get("cc")
        )

        return {
            "source_id": source.id,
            "external_id": source.external_id,
            "thread_id": (
                payload.get("threadId")
                or source.external_parent_id
            ),
            "source_label": source.source_label,
            "date": payload.get("date"),
            "subject": payload.get("subject"),
            "from": from_value,
            "to": to_values,
            "cc": cc_values,
            "text": payload.get("text"),
            "message_id": payload.get("messageId"),
            "size_estimate": payload.get("sizeEstimate"),
            "client_matching": (
                matching if isinstance(matching, dict) else None
            ),
            "created_at": self._serialize_datetime(
                source.created_at
            ),
        }

    def _normalize_sheets_source(
        self,
        source: Any,
    ) -> dict[str, Any]:
        payload = source.raw_payload or {}

        return {
            "source_id": source.id,
            "external_id": source.external_id,
            "source_label": source.source_label,
            "source_url": source.source_url,
            "row_data": payload,
            "created_at": self._serialize_datetime(
                source.created_at
            ),
            "updated_at": self._serialize_datetime(
                source.updated_at
            ),
        }

    def _normalize_generic_source(
        self,
        source: Any,
    ) -> dict[str, Any]:
        return {
            "source_id": source.id,
            "source_type": source.source_type,
            "external_id": source.external_id,
            "external_parent_id": source.external_parent_id,
            "source_label": source.source_label,
            "source_url": source.source_url,
            "extracted_text": source.extracted_text,
            "raw_payload": source.raw_payload,
            "created_at": self._serialize_datetime(
                source.created_at
            ),
            "updated_at": self._serialize_datetime(
                source.updated_at
            ),
        }

    def _normalize_document(
        self,
        document: Any,
    ) -> dict[str, Any]:
        return {
            "id": document.id,
            "filename": document.filename,
            "original_filename": document.original_filename,
            "content_type": document.content_type,
            "file_size": document.file_size,
            "source_type": document.source_type,
            "external_id": document.external_id,
            "gmail_message_id": document.gmail_message_id,
            "gmail_thread_id": document.gmail_thread_id,
            "candidate_id": document.candidate_id,
            "client_id": document.client_id,
            "processing_status": document.processing_status,
            "processing_error": document.processing_error,
            "extracted_text": document.extracted_text,
            "match_status": document.match_status,
            "match_confidence": document.match_confidence,
            "match_method": document.match_method,
            "matched_at": self._serialize_datetime(
                document.matched_at
            ),
            "captured_at": self._serialize_datetime(
                document.captured_at
            ),
            "latitude": document.latitude,
            "longitude": document.longitude,
            "location_accuracy_m": document.location_accuracy_m,
            "location_source": document.location_source,
            "inspection_session_id": (
                document.inspection_session_id
            ),
            "created_at": self._serialize_datetime(
                document.created_at
            ),
            "updated_at": self._serialize_datetime(
                document.updated_at
            ),
        }

    @staticmethod
    def _extract_mail_address(
        value: Any,
    ) -> dict[str, str | None] | None:
        if not isinstance(value, dict):
            return None

        entries = value.get("value")

        if not isinstance(entries, list) or not entries:
            text_value = value.get("text")

            if text_value:
                return {
                    "name": None,
                    "address": str(text_value),
                }

            return None

        first = entries[0]

        if not isinstance(first, dict):
            return None

        return {
            "name": first.get("name"),
            "address": first.get("address"),
        }

    @staticmethod
    def _extract_mail_addresses(
        value: Any,
    ) -> list[dict[str, str | None]]:
        if not isinstance(value, dict):
            return []

        entries = value.get("value")

        if not isinstance(entries, list):
            return []

        result: list[dict[str, str | None]] = []

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            result.append(
                {
                    "name": entry.get("name"),
                    "address": entry.get("address"),
                }
            )

        return result

    @staticmethod
    def _serialize_datetime(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        isoformat = getattr(
            value,
            "isoformat",
            None,
        )

        if callable(isoformat):
            return isoformat()

        return str(value)
