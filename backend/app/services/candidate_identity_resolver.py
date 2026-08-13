from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate


EMAIL_RE = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)

WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class IdentityEvidence:
    value: str
    method: str
    source_id: int
    source_type: str


@dataclass
class IdentityResolution:
    candidate_id: int
    current_name: str
    status: str

    proposed_name: str | None = None
    confidence: float = 0.0
    reason: str | None = None

    evidence: list[IdentityEvidence] = field(
        default_factory=list
    )


class CandidateIdentityResolver:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def resolve(
        self,
        candidate: ClientCandidate,
    ) -> IdentityResolution:
        sources = (
            self.db.query(CandidateSource)
            .filter(
                CandidateSource.candidate_id
                == candidate.id,
                CandidateSource.deleted_at.is_(None),
            )
            .order_by(
                CandidateSource.created_at.asc(),
                CandidateSource.id.asc(),
            )
            .all()
        )

        full_names: list[IdentityEvidence] = []
        partial_names: list[IdentityEvidence] = []
        ambiguous_sheet_rows: list[IdentityEvidence] = []

        for source in sources:
            if source.source_type != "google_sheets_row":
                continue

            payload = source.raw_payload or {}

            first_name = self._find_value(
                payload,
                (
                    "imię",
                    "imie",
                    "first name",
                    "firstname",
                ),
            )

            last_name = self._find_value(
                payload,
                (
                    "nazwisko",
                    "last name",
                    "lastname",
                    "surname",
                ),
            )

            first_name = self._clean_text(
                first_name
            )

            last_name = self._clean_text(
                last_name
            )

            if first_name and last_name:
                first_parts = first_name.split()

                if len(first_parts) > 1:
                    ambiguous_sheet_rows.append(
                        IdentityEvidence(
                            value=(
                                f"{first_name} "
                                f"{last_name}"
                            ),
                            method=(
                                "sheet_multiple_first_names"
                            ),
                            source_id=source.id,
                            source_type=source.source_type,
                        )
                    )

                    continue

                full_names.append(
                    IdentityEvidence(
                        value=self._clean_text(
                            f"{first_name} {last_name}"
                        ),
                        method="sheet_first_last",
                        source_id=source.id,
                        source_type=source.source_type,
                    )
                )

                continue

            if first_name:
                partial_names.append(
                    IdentityEvidence(
                        value=first_name,
                        method="sheet_first_name",
                        source_id=source.id,
                        source_type=source.source_type,
                    )
                )

            if last_name:
                partial_names.append(
                    IdentityEvidence(
                        value=last_name,
                        method="sheet_last_name",
                        source_id=source.id,
                        source_type=source.source_type,
                    )
                )

        unique_full_names = self._unique_names(
            full_names
        )

        if ambiguous_sheet_rows:
            return IdentityResolution(
                candidate_id=candidate.id,
                current_name=candidate.name,
                status="ambiguous",
                confidence=0.0,
                reason=(
                    "Structured source contains multiple "
                    "first names in one contact field."
                ),
                evidence=(
                    full_names
                    + partial_names
                    + ambiguous_sheet_rows
                ),
            )

        if len(unique_full_names) > 1:
            return IdentityResolution(
                candidate_id=candidate.id,
                current_name=candidate.name,
                status="ambiguous",
                confidence=0.0,
                reason=(
                    "Multiple distinct full names were found "
                    "for the same candidate."
                ),
                evidence=(
                    full_names
                    + partial_names
                ),
            )

        if len(unique_full_names) == 1:
            proposed_name = next(
                iter(unique_full_names)
            )

            matching = [
                item
                for item in full_names
                if self._normalize_name(
                    item.value
                )
                == self._normalize_name(
                    proposed_name
                )
            ]

            confidence = (
                0.99
                if len(matching) >= 2
                else 0.97
            )

            return IdentityResolution(
                candidate_id=candidate.id,
                current_name=candidate.name,
                proposed_name=proposed_name,
                status="auto_safe",
                confidence=confidence,
                reason=(
                    "Unique full name found in structured "
                    "Google Sheets evidence."
                ),
                evidence=(
                    full_names
                    + partial_names
                ),
            )

        partial_values = {
            self._normalize_name(item.value): item.value
            for item in partial_names
            if item.value
        }

        current_name = self._clean_text(
            candidate.name
        )

        if (
            current_name
            and not self._looks_like_email(
                current_name
            )
            and len(current_name.split()) == 1
        ):
            current_normalized = (
                self._normalize_name(
                    current_name
                )
            )

            other_parts = [
                item.value
                for key, item in (
                    (
                        self._normalize_name(
                            evidence.value
                        ),
                        evidence,
                    )
                    for evidence
                    in partial_names
                )
                if key != current_normalized
            ]

            unique_other_parts = {
                self._normalize_name(value): value
                for value in other_parts
            }

            if len(unique_other_parts) == 1:
                other_value = next(
                    iter(
                        unique_other_parts.values()
                    )
                )

                proposed_name = (
                    f"{other_value} "
                    f"{current_name}"
                )

                return IdentityResolution(
                    candidate_id=candidate.id,
                    current_name=candidate.name,
                    proposed_name=(
                        self._clean_text(
                            proposed_name
                        )
                    ),
                    status="review",
                    confidence=0.75,
                    reason=(
                        "Candidate has one existing name part "
                        "and one complementary structured part, "
                        "but no full-name source."
                    ),
                    evidence=partial_names,
                )

        if partial_values:
            best_partial = next(
                iter(
                    partial_values.values()
                )
            )

            return IdentityResolution(
                candidate_id=candidate.id,
                current_name=candidate.name,
                proposed_name=best_partial,
                status="insufficient",
                confidence=0.60,
                reason=(
                    "Only partial structured identity "
                    "information is available."
                ),
                evidence=partial_names,
            )

        return IdentityResolution(
            candidate_id=candidate.id,
            current_name=candidate.name,
            status="insufficient",
            confidence=0.0,
            reason=(
                "No reliable structured full-name "
                "evidence was found."
            ),
            evidence=[],
        )

    @classmethod
    def _find_value(
        cls,
        payload: dict[str, Any],
        aliases: tuple[str, ...],
    ) -> Any:
        normalized_aliases = {
            cls._normalize_key(alias)
            for alias in aliases
        }

        for key, value in payload.items():
            if (
                cls._normalize_key(
                    str(key)
                )
                in normalized_aliases
            ):
                return value

        return None

    @staticmethod
    def _clean_text(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        return WHITESPACE_RE.sub(
            " ",
            str(value).strip(),
        )

    @staticmethod
    def _looks_like_email(
        value: str,
    ) -> bool:
        return bool(
            EMAIL_RE.match(
                value.strip().lower()
            )
        )

    @staticmethod
    def _normalize_name(
        value: str,
    ) -> str:
        return WHITESPACE_RE.sub(
            " ",
            value.strip().lower(),
        )

    @staticmethod
    def _normalize_key(
        value: str,
    ) -> str:
        normalized = unicodedata.normalize(
            "NFKD",
            value,
        )

        without_marks = "".join(
            character
            for character in normalized
            if not unicodedata.combining(
                character
            )
        )

        return "".join(
            character
            for character in without_marks.lower()
            if character.isalnum()
        )

    @classmethod
    def _unique_names(
        cls,
        evidence: list[IdentityEvidence],
    ) -> set[str]:
        result: dict[str, str] = {}

        for item in evidence:
            normalized = cls._normalize_name(
                item.value
            )

            if normalized:
                result.setdefault(
                    normalized,
                    item.value,
                )

        return set(
            result.values()
        )
