from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_page import DocumentPage
from app.repositories.import_repository import ImportRepository
from app.schemas.import_ingest import (
    CandidateDataInput,
    CandidateSourceInput,
    ImportIngestRequest,
)
from app.services.email_client_matching_service import (
    EMAIL_MATCH_METADATA_KEY,
    EmailClientMatchingService,
)
from app.services.forward_client_contact_service import ForwardClientContactService
from app.services.forward_source_ingestion_service import ForwardSourceIngestionService


@dataclass(frozen=True)
class EmailAttachmentReconciliationResult:
    status: str
    candidate_id: int | None = None
    client_id: int | None = None


class EmailAttachmentReconciliationService:
    """Re-evaluate one future Gmail message after its attachment is processed.

    Historical sources are excluded by requiring Matching V2 metadata that is
    written only during new-message ingestion. No scan or retry is performed.
    """

    MAX_PAGES = 8
    MAX_TEXT_CHARS = 10_000

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ImportRepository(db)

    def reconcile(self, document_id: int) -> EmailAttachmentReconciliationResult:
        document = (
            self.db.query(Document)
            .filter(Document.id == document_id)
            .first()
        )
        if (
            document is None
            or document.source_type != "gmail_attachment"
            or not document.vision_auto_eligible
            or not document.gmail_message_id
            or not document.candidate_id
        ):
            return EmailAttachmentReconciliationResult("not_applicable")

        source = (
            self.db.query(CandidateSource)
            .filter(
                CandidateSource.candidate_id == document.candidate_id,
                CandidateSource.source_type == "gmail_message",
                CandidateSource.external_id == document.gmail_message_id,
                CandidateSource.deleted_at.is_(None),
            )
            .first()
        )
        payload = source.raw_payload if source and isinstance(source.raw_payload, dict) else {}
        if source is None or not isinstance(payload.get(EMAIL_MATCH_METADATA_KEY), dict):
            return EmailAttachmentReconciliationResult("historical_or_unversioned")

        candidate = (
            self.db.query(ClientCandidate)
            .filter(
                ClientCandidate.id == document.candidate_id,
                ClientCandidate.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )
        if candidate is None:
            return EmailAttachmentReconciliationResult("candidate_missing")
        # A pending Gmail Candidate is intentionally one-message-per-candidate
        # in V2. Refuse automatic reconciliation if older grouping violates
        # that ownership boundary.
        source_count = (
            self.db.query(CandidateSource.id)
            .filter(
                CandidateSource.candidate_id == candidate.id,
                CandidateSource.source_type == "gmail_message",
                CandidateSource.deleted_at.is_(None),
            )
            .count()
        )
        if source_count != 1 and candidate.matched_client_id is None:
            return EmailAttachmentReconciliationResult(
                "review_multiple_sources", candidate.id
            )

        message_documents = (
            self.db.query(Document)
            .filter(
                Document.candidate_id == candidate.id,
                Document.gmail_message_id == source.external_id,
            )
            .order_by(Document.id.asc())
            .with_for_update()
            .all()
        )
        if any(
            item.processing_status in {"stored", "pending", "extracting"}
            for item in message_documents
        ):
            return EmailAttachmentReconciliationResult(
                "waiting_for_attachments", candidate.id, candidate.matched_client_id
            )

        request = self._request(candidate, source, message_documents)
        decision = EmailClientMatchingService(self.repository).match(request)
        updated_payload = dict(payload)
        updated_payload[EMAIL_MATCH_METADATA_KEY] = decision.metadata()

        current_client_id = candidate.matched_client_id
        if current_client_id is not None:
            supports_current = current_client_id in decision.candidate_client_ids
            conflicts = (
                decision.contradictory
                or (
                    decision.confidence == "certain"
                    and decision.client is not None
                    and decision.client.id != current_client_id
                )
                or (
                    decision.candidate_client_ids
                    and not supports_current
                )
            )
            if conflicts:
                conflict_metadata = dict(updated_payload[EMAIL_MATCH_METADATA_KEY])
                conflict_metadata.update(
                    {
                        "confidence": "ambiguous",
                        "matched_client_id": current_client_id,
                        "existing_link_conflict": True,
                        "reasons": list(
                            dict.fromkeys(
                                [
                                    *conflict_metadata.get("reasons", []),
                                    "existing_link_conflict",
                                ]
                            )
                        ),
                    }
                )
                updated_payload[EMAIL_MATCH_METADATA_KEY] = conflict_metadata
                for linked_document in message_documents:
                    linked_document.match_status = "suggested"
                    linked_document.match_method = "email_matching_v2_conflict"
                    self.db.add(linked_document)
                source.raw_payload = updated_payload
                self.db.add(source)
                self.db.commit()
                return EmailAttachmentReconciliationResult(
                    "review_existing_link_conflict",
                    candidate.id,
                    current_client_id,
                )
            source.raw_payload = updated_payload
            self.db.add(source)
            self.db.commit()
            return EmailAttachmentReconciliationResult(
                "already_linked", candidate.id, current_client_id
            )

        source.raw_payload = updated_payload
        self.db.add(source)

        if decision.confidence != "certain" or decision.client is None:
            self.db.commit()
            return EmailAttachmentReconciliationResult(
                f"review_{decision.confidence}", candidate.id
            )

        target = decision.client
        document_conflicts = [
            item for item in message_documents
            if item.client_id not in {None, target.id}
        ]
        if document_conflicts:
            conflict_metadata = dict(updated_payload[EMAIL_MATCH_METADATA_KEY])
            conflict_metadata.update(
                {
                    "confidence": "ambiguous",
                    "matched_client_id": None,
                    "existing_document_link_conflict": True,
                    "reasons": list(
                        dict.fromkeys(
                            [
                                *conflict_metadata.get("reasons", []),
                                "existing_document_link_conflict",
                            ]
                        )
                    ),
                }
            )
            source.raw_payload = {
                **updated_payload,
                EMAIL_MATCH_METADATA_KEY: conflict_metadata,
            }
            self.db.add(source)
            for linked_document in document_conflicts:
                linked_document.match_status = "suggested"
                linked_document.match_method = "email_matching_v2_conflict"
                self.db.add(linked_document)
            self.db.commit()
            return EmailAttachmentReconciliationResult(
                "review_document_conflict", candidate.id
            )

        candidate.status = "duplicate"
        candidate.matched_client_id = target.id
        self.db.add(candidate)
        ForwardClientContactService.add_from_payloads(
            target,
            [updated_payload],
            source_id=source.id,
            source_type="gmail_message",
        )
        for linked_document in message_documents:
            linked_document.client_id = target.id
            linked_document.match_status = "matched"
            linked_document.match_confidence = 1.0
            linked_document.match_method = "email_matching_v2_attachment"
            linked_document.matched_at = datetime.now(UTC)
            self.db.add(linked_document)
        self.db.commit()
        return EmailAttachmentReconciliationResult(
            "linked_certain", candidate.id, target.id
        )

    def _request(
        self,
        candidate: ClientCandidate,
        source: CandidateSource,
        documents: list[Document],
    ) -> ImportIngestRequest:
        payload = dict(source.raw_payload or {})
        payload["attachments"] = [
            self._attachment(document) for document in documents
        ]
        request = ImportIngestRequest(
            import_source_id=source.import_source_id,
            import_run_id=source.import_run_id,
            candidate=CandidateDataInput(
                client_type=candidate.client_type,
                name=candidate.name,
                legal_name=candidate.legal_name,
                tax_id=candidate.tax_id,
                registration_number=candidate.registration_number,
                industry_id=candidate.industry_id,
                website=candidate.website,
                primary_email=candidate.primary_email,
                primary_phone=candidate.primary_phone,
                street=candidate.street,
                building_number=candidate.building_number,
                unit_number=candidate.unit_number,
                postal_code=candidate.postal_code,
                city=candidate.city,
                country_code=candidate.country_code,
                notes=None,
                confidence=candidate.confidence,
            ),
            source=CandidateSourceInput(
                source_type="gmail_message",
                external_id=source.external_id,
                external_parent_id=source.external_parent_id,
                source_label=source.source_label,
                source_url=source.source_url,
                extracted_text=source.extracted_text,
                raw_payload=payload,
            ),
        )
        return ForwardSourceIngestionService().prepare(request)

    def _attachment(self, document: Document) -> dict[str, object]:
        pages = (
            self.db.query(DocumentPage)
            .filter(DocumentPage.document_id == document.id)
            .order_by(DocumentPage.page_number.asc())
            .limit(self.MAX_PAGES)
            .all()
        )
        assets = (
            self.db.query(DocumentAsset)
            .filter(DocumentAsset.document_id == document.id)
            .order_by(DocumentAsset.id.asc())
            .limit(self.MAX_PAGES)
            .all()
        )
        extracted = self._join(
            [document.extracted_text]
            + [page.extracted_text for page in pages]
        )
        ocr = self._join(
            [page.ocr_text for page in pages]
            + [asset.ocr_text for asset in assets]
        )
        vision = self._join(
            [page.vision_analysis for page in pages]
            + [asset.vision_analysis for asset in assets]
        )
        return {
            "content_type": document.content_type or "",
            "extracted_text": extracted,
            "ocr_text": ocr,
            "vision_visible_text": vision,
        }

    @classmethod
    def _join(cls, values: list[str | None]) -> str:
        result: list[str] = []
        remaining = cls.MAX_TEXT_CHARS
        for value in values:
            text = " ".join(str(value or "").split())
            if not text or remaining <= 0:
                continue
            chunk = text[:remaining]
            result.append(chunk)
            remaining -= len(chunk)
        return "\n".join(result)
