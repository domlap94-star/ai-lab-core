from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.services.client_entity_projection_policy_service import (
    ClientEntityProjectionPolicyService,
)
from app.services.client_source_record_date_service import (
    ClientSourceRecordDateService,
)
from app.services.gmail_message_boundary_service import GmailMessageBoundaryService


LINKED_STATUSES = ("accepted", "merged", "duplicate")
SHEET_IDENTITY_KEYS = {
    "IMIE", "NAZWISKO", "E MAIL", "EMAIL", "TELEFON", "NIP",
    "NAZWA", "NAZWA FIRMY", "FIRMA", "WWW", "STRONA WWW",
    "ULICA", "MIASTO", "KOD POCZTOWY", "DATA",
}


class ClientReconstructionEvidenceService:
    """Builds minimized, deterministic, read-only evidence packets."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.projection = ClientEntityProjectionPolicyService(db)
        self.source_dates = ClientSourceRecordDateService(db)
        self.boundary = GmailMessageBoundaryService()

    def build(self, client_id: int) -> dict[str, Any]:
        client = self.db.query(Client).filter(
            Client.id == client_id, Client.deleted_at.is_(None)
        ).one()
        candidates = self.db.query(ClientCandidate).filter(
            ClientCandidate.matched_client_id == client_id,
            ClientCandidate.deleted_at.is_(None),
            ClientCandidate.status.in_(LINKED_STATUSES),
        ).order_by(ClientCandidate.id).all()
        candidate_ids = [item.id for item in candidates]
        sources = [] if not candidate_ids else self.db.query(CandidateSource).filter(
            CandidateSource.candidate_id.in_(candidate_ids),
            CandidateSource.deleted_at.is_(None),
            CandidateSource.source_type.in_(("gmail_message", "google_sheets_row")),
        ).order_by(CandidateSource.id).all()
        by_candidate: dict[int, list[CandidateSource]] = {}
        for source in sources:
            by_candidate.setdefault(source.candidate_id, []).append(source)

        projections = []
        evidence = []
        for candidate in candidates:
            item = self.projection.project(
                candidate, include_candidate_name_evidence=False
            )
            projections.append({
                "candidate_id": candidate.id, "status": candidate.status,
                "projection_status": item.status, "entity_name": item.entity_name,
                "entity_type": item.entity_type, "legal_name": item.legal_name,
                "contact_name": item.contact_name, "contact_email": item.contact_email,
                "contact_phone": item.contact_phone, "tax_id": item.tax_id,
                "confidence": item.confidence,
                "evidence": [vars(value) for value in item.evidence],
            })
            for source in by_candidate.get(candidate.id, []):
                normalized = self._source(source)
                if normalized:
                    evidence.append(normalized)

        source_date = self.source_dates.get_for_client_ids([client.id]).get(client.id)
        packet = {
            "client": {
                "id": client.id, "client_type": client.client_type,
                "name": client.name, "legal_name": client.legal_name,
                "tax_id": client.tax_id, "email": client.primary_email,
                "phone": client.primary_phone, "website": client.website,
                "address": {"street": client.street, "building_number": client.building_number,
                            "unit_number": client.unit_number, "postal_code": client.postal_code,
                            "city": client.city, "country_code": client.country_code},
                "source_record_date": source_date.isoformat() if source_date else None,
            },
            "candidate_links": [{"candidate_id": item.id, "status": item.status,
                                  "source_ids": [s.id for s in by_candidate.get(item.id, [])]}
                                 for item in candidates],
            "deterministic_projections": projections,
            "source_evidence": evidence,
        }
        return packet

    def _source(self, source: CandidateSource) -> dict[str, Any] | None:
        payload = source.raw_payload if isinstance(source.raw_payload, dict) else {}
        base = {"source_id": source.id, "source_type": source.source_type}
        if source.source_type == "google_sheets_row":
            fields = {}
            for key, value in payload.items():
                normalized = unicodedata.normalize("NFKD", str(key))
                normalized = "".join(char for char in normalized if not unicodedata.combining(char))
                normalized = " ".join(normalized.strip().upper().replace("-", " ").split())
                if normalized in SHEET_IDENTITY_KEYS and isinstance(value, (str, int, float)):
                    fields[str(key)] = str(value).strip()
            return {**base, "fields": fields}
        raw_text = next((payload.get(key) for key in ("text", "textPlain", "body_text")
                         if isinstance(payload.get(key), str)), "")
        boundary = self.boundary.parse(raw_text)
        sender = self._addresses(payload.get("from"))
        return {
            **base,
            "external_message_ref": hashlib.sha256(source.external_id.encode()).hexdigest()[:16],
            "date": payload.get("date"), "direction": payload.get("direction"),
            "sender": sender[:1], "recipients": self._addresses(payload.get("to")),
            "subject": payload.get("subject"),
            "current_author_excerpt": boundary.current_content[:1200],
            "relay": boundary.relay_payload is not None,
        }

    @staticmethod
    def _addresses(value: Any) -> list[dict[str, str | None]]:
        if not isinstance(value, dict) or not isinstance(value.get("value"), list):
            return []
        return [{"name": item.get("name"), "address": item.get("address")}
                for item in value["value"] if isinstance(item, dict)]

    @staticmethod
    def sha256(packet: dict[str, Any]) -> str:
        encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
