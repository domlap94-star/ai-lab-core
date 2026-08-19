from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.models.client import Client
from app.repositories.import_repository import ImportRepository
from app.schemas.import_ingest import ImportIngestRequest
from app.services.forward_source_ingestion_service import (
    CONTACT_METADATA_KEY,
    ForwardSourceIngestionService,
    PHONE_RE,
    TAX_ID_RE,
)


EMAIL_MATCH_METADATA_KEY = "_next_stabil_email_client_match_v2"
MatchConfidence = Literal["certain", "high", "ambiguous", "unresolved"]


@dataclass(frozen=True)
class _EvidenceGroup:
    reason: str
    client_ids: frozenset[int]
    strong: bool


@dataclass(frozen=True)
class EmailClientMatch:
    client: Client | None
    confidence: MatchConfidence
    reasons: tuple[str, ...]
    candidate_client_ids: tuple[int, ...]
    contradictory: bool
    vision_required: bool
    evidence_by_client: tuple[tuple[int, tuple[str, ...]], ...]

    def metadata(self) -> dict[str, object]:
        return {
            "version": "NEXT_STABIL_EMAIL_CLIENT_MATCH_V2",
            "confidence": self.confidence,
            "matched_client_id": self.client.id if self.client else None,
            "candidate_client_ids": list(self.candidate_client_ids),
            "reasons": list(self.reasons),
            "contradictory": self.contradictory,
            "vision_required": self.vision_required,
            "evidence": [
                {"client_id": client_id, "reasons": list(reasons)}
                for client_id, reasons in self.evidence_by_client
            ],
        }


class EmailClientMatchingService:
    """Bounded, deterministic matching for newly ingested Gmail messages.

    The service never invokes OCR, Vision or an LLM. It consumes only evidence
    already present at the ingestion boundary and returns review metadata when
    stronger evidence is unavailable. Only ``certain`` may auto-link.
    """

    MAX_CLIENTS = 10
    QUERY_LIMIT = MAX_CLIENTS + 1
    MAX_BODY_CHARS = 20_000
    MAX_ATTACHMENTS = 3
    MAX_ATTACHMENT_TEXT_CHARS = 10_000

    def __init__(self, repository: ImportRepository) -> None:
        self.repository = repository

    def match(self, request: ImportIngestRequest) -> EmailClientMatch:
        payload = request.source.raw_payload or {}
        metadata = payload.get(CONTACT_METADATA_KEY)
        metadata = metadata if isinstance(metadata, dict) else {}
        groups: list[_EvidenceGroup] = []
        overflow = False

        def add(reason: str, clients: list[Client], *, strong: bool) -> None:
            nonlocal overflow
            if len(clients) > self.MAX_CLIENTS:
                overflow = True
            ids = frozenset(client.id for client in clients[: self.MAX_CLIENTS])
            if ids:
                groups.append(_EvidenceGroup(reason, ids, strong))

        sender_email = self._clean(metadata.get("sender_email"))
        if sender_email:
            add(
                "exact_sender_email",
                self.repository.find_clients_by_email(
                    sender_email, limit=self.QUERY_LIMIT
                ),
                strong=True,
            )

        if request.candidate.tax_id:
            add(
                "exact_tax_id",
                self.repository.find_clients_by_tax_id(
                    request.candidate.tax_id, limit=self.QUERY_LIMIT
                ),
                strong=True,
            )
        if request.candidate.registration_number:
            add(
                "exact_reference_id",
                self.repository.find_clients_by_registration_number(
                    request.candidate.registration_number,
                    limit=self.QUERY_LIMIT,
                ),
                strong=True,
            )

        sender_first_party = metadata.get("sender_first_party") is True
        for value in self._strings(metadata.get("body_phones"), limit=8):
            add(
                "exact_phone_in_body",
                self.repository.find_clients_by_phone(
                    value, limit=self.QUERY_LIMIT
                ),
                strong=not sender_first_party,
            )
        for value in self._strings(metadata.get("body_tax_ids"), limit=8):
            add(
                "exact_tax_id_in_body",
                self.repository.find_clients_by_tax_id(
                    value, limit=self.QUERY_LIMIT
                ),
                strong=True,
            )
        for value in self._strings(metadata.get("body_emails"), limit=8):
            if value == sender_email:
                continue
            add(
                "exact_email_in_body",
                self.repository.find_clients_by_email(
                    value, limit=self.QUERY_LIMIT
                ),
                strong=False,
            )

        thread_id = self._clean(request.source.external_parent_id)
        if thread_id:
            thread_ids = self.repository.find_thread_client_ids(
                import_source_id=request.import_source_id,
                external_parent_id=thread_id,
                exclude_external_id=request.source.external_id,
                limit=self.QUERY_LIMIT,
            )
            add(
                "known_thread_relation",
                self.repository.get_clients_by_ids(thread_ids),
                strong=False,
            )

        if request.candidate.name:
            add(
                "exact_name_city",
                self.repository.find_clients_by_name_city(
                    name=request.candidate.name,
                    city=request.candidate.city,
                    limit=self.QUERY_LIMIT,
                ),
                strong=False,
            )

        (
            attachment_groups,
            vision_required,
            attachment_overflow,
        ) = self._attachment_groups(payload)
        overflow = overflow or attachment_overflow
        for reason, kind, value in attachment_groups:
            if kind == "tax":
                clients = self.repository.find_clients_by_tax_id(
                    value, limit=self.QUERY_LIMIT
                )
            elif kind == "phone":
                clients = self.repository.find_clients_by_phone(
                    value, limit=self.QUERY_LIMIT
                )
            else:
                clients = self.repository.find_clients_by_email(
                    value, limit=self.QUERY_LIMIT
                )
            add(reason, clients, strong=(kind in {"tax", "phone"}))

        return self._resolve(groups, overflow=overflow, vision_required=vision_required)

    def _resolve(
        self,
        groups: list[_EvidenceGroup],
        *,
        overflow: bool,
        vision_required: bool,
    ) -> EmailClientMatch:
        reasons_by_client: dict[int, set[str]] = {}
        for group in groups:
            for client_id in group.client_ids:
                reasons_by_client.setdefault(client_id, set()).add(group.reason)

        all_ids = set(reasons_by_client)
        strong_groups = [group for group in groups if group.strong]
        weak_groups = [group for group in groups if not group.strong]
        selected_id: int | None = None
        contradictory = overflow

        if strong_groups:
            intersection = set(strong_groups[0].client_ids)
            for group in strong_groups[1:]:
                intersection.intersection_update(group.client_ids)
            if len(intersection) == 1:
                selected_id = next(iter(intersection))
                if any(
                    selected_id not in group.client_ids for group in weak_groups
                ):
                    contradictory = True
                    selected_id = None
            else:
                contradictory = len(all_ids) > 1 or overflow
        elif len(all_ids) > 1:
            contradictory = True

        if selected_id is not None and not contradictory and not vision_required:
            confidence: MatchConfidence = "certain"
        elif selected_id is not None and not contradictory:
            confidence = "high"
        elif contradictory:
            confidence = "ambiguous"
        elif len(all_ids) == 1:
            confidence = "high"
        else:
            confidence = "unresolved"

        ordered_ids = tuple(sorted(all_ids)[: self.MAX_CLIENTS])
        evidence = tuple(
            (client_id, tuple(sorted(reasons_by_client[client_id])))
            for client_id in ordered_ids
        )
        client = None
        if confidence == "certain" and selected_id is not None:
            rows = self.repository.get_clients_by_ids([selected_id])
            client = rows[0] if rows else None
            if client is None:
                confidence = "unresolved"

        reasons = tuple(
            sorted({reason for values in reasons_by_client.values() for reason in values})
        )
        if contradictory:
            reasons = (*reasons, "contradictory_evidence")
        if overflow:
            reasons = (*reasons, "match_limit_exceeded")
        return EmailClientMatch(
            client=client,
            confidence=confidence,
            reasons=tuple(dict.fromkeys(reasons)),
            candidate_client_ids=ordered_ids,
            contradictory=contradictory,
            vision_required=vision_required,
            evidence_by_client=evidence,
        )

    def _attachment_groups(
        self, payload: dict[str, Any]
    ) -> tuple[list[tuple[str, str, str]], bool, bool]:
        raw_attachments = payload.get("attachments")
        if not isinstance(raw_attachments, list):
            return [], False, False
        groups: list[tuple[str, str, str]] = []
        vision_required = False
        for item in raw_attachments[: self.MAX_ATTACHMENTS]:
            if not isinstance(item, dict):
                continue
            texts: list[tuple[str, str]] = []
            for field, source in (
                ("extracted_text", "attachment_text"),
                ("ocr_text", "attachment_ocr"),
                ("vision_visible_text", "attachment_vision"),
            ):
                value = item.get(field)
                if isinstance(value, str) and value.strip():
                    texts.append((source, value[: self.MAX_ATTACHMENT_TEXT_CHARS]))
            content_type = self._clean(item.get("content_type")).casefold()
            if content_type.startswith("image/") and not texts:
                vision_required = True
            for source, text in texts:
                groups.extend(self._text_groups(text, source))
        return groups, vision_required, len(raw_attachments) > self.MAX_ATTACHMENTS

    @staticmethod
    def _text_groups(text: str, source: str) -> list[tuple[str, str, str]]:
        groups: list[tuple[str, str, str]] = []
        for match in TAX_ID_RE.finditer(text):
            value = ForwardSourceIngestionService.normalize_tax_id(match.group(1))
            if value:
                groups.append((f"exact_tax_id_in_{source}", "tax", value))
        for match in PHONE_RE.finditer(text):
            value = ForwardSourceIngestionService.normalize_phone(match.group(0))
            if value:
                groups.append((f"exact_phone_in_{source}", "phone", value))
        for value in ForwardSourceIngestionService.parse_emails(text).values[:8]:
            groups.append((f"exact_email_in_{source}", "email", value))
        return groups

    @staticmethod
    def _clean(value: object) -> str:
        return " ".join(str(value or "").split())

    @staticmethod
    def _strings(value: object, *, limit: int) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        return tuple(
            " ".join(item.split())
            for item in value[:limit]
            if isinstance(item, str) and item.strip()
        )
