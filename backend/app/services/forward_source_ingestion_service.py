from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.schemas.import_ingest import CandidateSourceInput, ImportIngestRequest
from app.services.candidate_identity_gmail_resolver import CandidateIdentityGmailResolver
from app.services.client_identity_name_quality_service import ClientIdentityNameQualityService
from app.services.first_party_identity_registry import FirstPartyIdentityRegistry
from app.services.gmail_message_boundary_service import GmailMessageBoundaryService


EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?48[\s.-]*)?(?:\d[\s.-]*){9}(?!\d)")
CONTACT_METADATA_KEY = "_next_stabil_forward_contacts_v1"


@dataclass(frozen=True)
class ContactParseResult:
    values: tuple[str, ...]
    ambiguous: bool = False


class ForwardSourceIngestionService:
    """Deterministic normalization applied only to newly ingested sources."""

    def __init__(self) -> None:
        self.gmail_boundary = GmailMessageBoundaryService()

    def prepare(self, request: ImportIngestRequest) -> ImportIngestRequest:
        data = request.candidate
        source = request.source
        emails = self.parse_emails(data.primary_email)
        phones = self.parse_phones(data.primary_phone)
        name = data.name
        notes = data.notes
        warnings = ["AMBIGUOUS_PHONE"] if phones.ambiguous else []

        if source.source_type == "gmail_message":
            # Gmail transport belongs to CandidateSource / Email History.
            # It is never a CRM note.
            notes = None
            gmail = self._prepare_gmail(source, data.primary_email)
            emails = ContactParseResult(
                self._unique((*emails.values, *gmail["emails"]))
            )
            phones = ContactParseResult(
                self._unique((*phones.values, *gmail["phones"]))
            )
            if self.is_usable_identity(gmail["name"]):
                name = gmail["name"]

        if not self.is_usable_identity(name):
            name = None

        candidate = data.model_copy(
            update={
                "name": name,
                "notes": notes,
                "primary_email": emails.values[0] if emails.values else None,
                "primary_phone": phones.values[0] if phones.values else None,
            }
        )
        payload = dict(source.raw_payload or {})
        payload[CONTACT_METADATA_KEY] = {
            "emails": list(emails.values),
            "phones": list(phones.values),
            "warnings": warnings,
        }
        prepared_source = source.model_copy(update={"raw_payload": payload})
        return request.model_copy(
            update={"candidate": candidate, "source": prepared_source}
        )

    def _prepare_gmail(
        self,
        source: CandidateSourceInput,
        candidate_email: str | None,
    ) -> dict[str, Any]:
        payload = source.raw_payload or {}
        raw_text = self._message_text(payload, source.extracted_text)
        current = self.gmail_boundary.parse(raw_text).current_content
        sender_email, sender_name = self._header_identity(payload, "from")
        normalized_candidate = self.normalize_email(candidate_email)
        sender_is_external_candidate = bool(
            sender_email
            and (not normalized_candidate or sender_email == normalized_candidate)
            and not FirstPartyIdentityRegistry.is_first_party_email(sender_email)
        )

        emails: list[str] = []
        phones: list[str] = []
        if sender_is_external_candidate:
            emails.append(sender_email)
            emails.extend(self.parse_emails(current).values)
            phones.extend(
                normalized
                for match in PHONE_RE.finditer(current)
                if (normalized := self.normalize_phone(match.group(0)))
            )

        name = sender_name if sender_is_external_candidate else None
        if not self.is_usable_identity(name) and sender_is_external_candidate:
            explicit_signature = self._explicit_signoff_identity(current)
            signatures = (
                [explicit_signature]
                if explicit_signature
                else CandidateIdentityGmailResolver._extract_signature_names(current)
            )
            usable = [value for value in signatures if self.is_usable_identity(value)]
            unique = {" ".join(value.casefold().split()) for value in usable}
            name = usable[0] if len(unique) == 1 else None

        return {
            "name": name,
            "emails": self._unique(emails),
            "phones": self._unique(phones),
        }

    @staticmethod
    def _explicit_signoff_identity(text: str) -> str | None:
        lines = [" ".join(line.split()) for line in text.splitlines()]
        lines = [line for line in lines if line]
        for index, line in enumerate(lines[-14:]):
            if not CandidateIdentityGmailResolver._is_signoff_only(line):
                continue
            tail = lines[-14:]
            if index + 1 >= len(tail):
                return None
            candidate = CandidateIdentityGmailResolver._normalize_signature_candidate(
                tail[index + 1]
            )
            if CandidateIdentityGmailResolver._valid_full_person_name(candidate):
                return candidate
            return None
        return None

    @classmethod
    def parse_emails(cls, value: str | None) -> ContactParseResult:
        if not value:
            return ContactParseResult(())
        values = [match.group(0).casefold() for match in EMAIL_RE.finditer(value)]
        return ContactParseResult(cls._unique(values))

    @classmethod
    def parse_phones(cls, value: str | None) -> ContactParseResult:
        if not value:
            return ContactParseResult(())
        text = value.strip()
        explicit = [part.strip() for part in re.split(r"[;,/\r\n]+", text) if part.strip()]
        if len(explicit) > 1:
            normalized = [cls.normalize_phone(part) for part in explicit]
            if all(normalized):
                return ContactParseResult(cls._unique(normalized))
            return ContactParseResult((), ambiguous=True)

        digits = re.sub(r"\D", "", text)
        if len(digits) == 18:
            return ContactParseResult((digits[:9], digits[9:]))
        if len(digits) == 22 and digits.startswith("48") and digits[11:13] == "48":
            return ContactParseResult((digits[2:11], digits[13:22]))
        single = cls.normalize_phone(text)
        return ContactParseResult((single,)) if single else ContactParseResult((), True)

    @staticmethod
    def normalize_phone(value: str | None) -> str:
        if not value:
            return ""
        digits = re.sub(r"\D", "", value)
        if len(digits) == 11 and digits.startswith("48"):
            digits = digits[2:]
        return digits if len(digits) == 9 else ""

    @staticmethod
    def normalize_email(value: Any) -> str:
        if not value:
            return ""
        match = EMAIL_RE.fullmatch(str(value).strip())
        return match.group(0).casefold() if match else ""

    @staticmethod
    def _message_text(payload: dict[str, Any], fallback: str | None) -> str:
        for key in ("text", "textPlain", "body_text", "snippet"):
            value = payload.get(key)
            if value:
                return str(value)
        return fallback or ""

    @classmethod
    def _header_identity(
        cls,
        payload: dict[str, Any],
        field_name: str,
    ) -> tuple[str, str]:
        field = payload.get(field_name)
        if not isinstance(field, dict) or not isinstance(field.get("value"), list):
            return "", ""
        for item in field["value"]:
            if not isinstance(item, dict):
                continue
            email = cls.normalize_email(item.get("address"))
            if email:
                return email, " ".join(str(item.get("name") or "").split())
        return "", ""

    @staticmethod
    def is_usable_identity(value: str | None) -> bool:
        if not value or not value.strip():
            return False
        text = " ".join(value.split())
        if not any(character.isalpha() for character in text):
            return False
        if any(character.isdigit() for character in text):
            return False
        if re.match(r"^\[\s*\d+\s*\]", text):
            return False
        if re.search(r"(?i)\.(?:png|jpe?g|pdf|docx?|xlsx?|zip)$", text):
            return False
        if ClientIdentityNameQualityService.suspicion_types(text):
            return False
        findings = ClientIdentityNameQualityService.additional_findings(text)
        if "ADDRESS_OR_LOCATION_AS_NAME" in findings:
            return False
        lowered = text.casefold()
        if lowered.startswith(
            (
                "dyrektor ",
                "wicedyrektor ",
                "prezes ",
                "kierownik ",
                "specjalista ",
                "manager ",
                "menedżer ",
            )
        ):
            return False
        if lowered.startswith(("oględziny ", "oferta ", "nie odbiera")):
            return False
        return not bool(EMAIL_RE.fullmatch(text))

    @staticmethod
    def _unique(values) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value for value in values if value))
