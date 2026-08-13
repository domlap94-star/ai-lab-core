from __future__ import annotations

import re
import unicodedata
from typing import Any

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.services.candidate_identity_resolver import (
    CandidateIdentityResolver,
    IdentityEvidence,
    IdentityResolution,
)


EMAIL_RE = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)

EMAIL_SPLIT_RE = re.compile(
    r"[._-]+"
)

ALPHA_TOKEN_RE = re.compile(
    r"^[A-Za-zÀ-žĄĆĘŁŃÓŚŹŻąćęłńóśźż]+$"
)


class CandidateIdentitySecondaryResolver:
    """
    Safe second-stage deterministic identity resolver.

    It enriches only candidates that the primary resolver
    classified as insufficient.

    Strong evidence:
    - Gmail full display name tied exactly to candidate email
    - structured first name from Google Sheets

    Medium evidence:
    - conservative email local-part patterns

    No database writes are performed here.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

        self.primary_resolver = (
            CandidateIdentityResolver(db)
        )

    def resolve(
        self,
        candidate: ClientCandidate,
    ) -> IdentityResolution:
        base = self.primary_resolver.resolve(
            candidate
        )

        if base.status != "insufficient":
            return base

        candidate_email = self._normalize_email(
            candidate.primary_email
        )

        if not candidate_email:
            return base

        first_names = self._sheet_first_names(
            base
        )

        gmail_names = self._gmail_display_names(
            candidate=candidate,
            candidate_email=candidate_email,
        )

        # ====================================================
        # 1. STRONG GMAIL DISPLAY NAME
        # ====================================================

        if gmail_names:
            unique_gmail = self._unique_values(
                [
                    item.value
                    for item in gmail_names
                ]
            )

            if len(unique_gmail) > 1:
                return IdentityResolution(
                    candidate_id=candidate.id,
                    current_name=candidate.name,
                    status="ambiguous",
                    confidence=0.0,
                    reason=(
                        "Multiple distinct valid Gmail "
                        "display names were found for the "
                        "candidate email."
                    ),
                    evidence=(
                        base.evidence
                        + gmail_names
                    ),
                )

            gmail_name = next(
                iter(
                    unique_gmail.values()
                )
            )

            gmail_first = (
                self._first_name_token(
                    gmail_name
                )
            )

            if len(first_names) == 1:
                sheet_first = next(
                    iter(
                        first_names.values()
                    )
                )

                if (
                    self._ascii_token(
                        sheet_first
                    )
                    == self._ascii_token(
                        gmail_first
                    )
                ):
                    return IdentityResolution(
                        candidate_id=candidate.id,
                        current_name=candidate.name,
                        proposed_name=gmail_name,
                        status="auto_safe",
                        confidence=0.99,
                        reason=(
                            "Valid full Gmail display name "
                            "is tied to the candidate email "
                            "and its first name matches "
                            "Google Sheets."
                        ),
                        evidence=(
                            base.evidence
                            + gmail_names
                        ),
                    )

            return IdentityResolution(
                candidate_id=candidate.id,
                current_name=candidate.name,
                proposed_name=gmail_name,
                status="review",
                confidence=0.90,
                reason=(
                    "Valid full Gmail display name is tied "
                    "to the candidate email, but structured "
                    "first-name corroboration is missing."
                ),
                evidence=(
                    base.evidence
                    + gmail_names
                ),
            )

        # ====================================================
        # 2. EMAIL LOCAL-PART
        # ====================================================

        if len(first_names) != 1:
            return base

        first_name = next(
            iter(
                first_names.values()
            )
        )

        (
            proposed_name,
            method,
            confidence,
        ) = self._derive_from_email(
            email=candidate_email,
            first_name=first_name,
        )

        if not proposed_name:
            return base

        return IdentityResolution(
            candidate_id=candidate.id,
            current_name=candidate.name,
            proposed_name=proposed_name,
            status="review",
            confidence=confidence,
            reason=(
                "Structured first name can be combined "
                "with a conservative deterministic pattern "
                "from the candidate email address."
            ),
            evidence=(
                base.evidence
                + [
                    IdentityEvidence(
                        value=proposed_name,
                        method=method,
                        source_id=0,
                        source_type="candidate_email",
                    )
                ]
            ),
        )

    # ========================================================
    # GMAIL
    # ========================================================

    def _gmail_display_names(
        self,
        *,
        candidate: ClientCandidate,
        candidate_email: str,
    ) -> list[IdentityEvidence]:
        sources = (
            self.db.query(CandidateSource)
            .filter(
                CandidateSource.candidate_id
                == candidate.id,
                CandidateSource.deleted_at.is_(None),
                CandidateSource.source_type
                == "gmail_message",
            )
            .order_by(
                CandidateSource.id.asc()
            )
            .all()
        )

        result: list[IdentityEvidence] = []

        for source in sources:
            payload = source.raw_payload or {}

            for field_name in (
                "from",
                "to",
                "cc",
            ):
                field = payload.get(
                    field_name
                )

                if not isinstance(
                    field,
                    dict,
                ):
                    continue

                entries = field.get(
                    "value"
                )

                if not isinstance(
                    entries,
                    list,
                ):
                    continue

                for entry in entries:
                    if not isinstance(
                        entry,
                        dict,
                    ):
                        continue

                    address = (
                        self._normalize_email(
                            entry.get(
                                "address"
                            )
                        )
                    )

                    if address != candidate_email:
                        continue

                    name = self._clean(
                        entry.get(
                            "name"
                        )
                    )

                    if not self._valid_full_person_name(
                        name
                    ):
                        continue

                    result.append(
                        IdentityEvidence(
                            value=name,
                            method="gmail_display_name",
                            source_id=source.id,
                            source_type=source.source_type,
                        )
                    )

        return result

    @classmethod
    def _valid_full_person_name(
        cls,
        value: str,
    ) -> bool:
        if not value:
            return False

        if cls._looks_like_email(
            value
        ):
            return False

        tokens = value.split()

        if len(tokens) < 2:
            return False

        for token in tokens:
            cleaned = token.strip(
                ".,;:()[]{}"
            )

            if len(cleaned) < 2:
                return False

            if not ALPHA_TOKEN_RE.match(
                cleaned
            ):
                return False

        return True

    # ========================================================
    # SHEETS
    # ========================================================

    @staticmethod
    def _sheet_first_names(
        base: IdentityResolution,
    ) -> dict[str, str]:
        result: dict[str, str] = {}

        for evidence in base.evidence:
            if evidence.method != "sheet_first_name":
                continue

            value = (
                CandidateIdentitySecondaryResolver
                ._clean(
                    evidence.value
                )
            )

            if not value:
                continue

            # A first-name field containing several tokens
            # is not safe enough for this stage.
            if len(value.split()) != 1:
                continue

            normalized = (
                CandidateIdentitySecondaryResolver
                ._ascii_token(
                    value
                )
            )

            if normalized:
                result.setdefault(
                    normalized,
                    value,
                )

        return result

    # ========================================================
    # EMAIL
    # ========================================================

    @classmethod
    def _derive_from_email(
        cls,
        *,
        email: str,
        first_name: str,
    ) -> tuple[
        str | None,
        str,
        float,
    ]:
        local_part = email.split(
            "@",
            1,
        )[0].lower()

        normalized_first = (
            cls._ascii_token(
                first_name
            )
        )

        if len(normalized_first) < 2:
            return None, "", 0.0

        tokens = [
            token
            for token in EMAIL_SPLIT_RE.split(
                local_part
            )
            if token
        ]

        # ----------------------------------------------------
        # More than 2 explicit segments:
        # maria.luiza.krecisz
        # mariuszprazanowski.mp
        #
        # Do not concatenate.
        # ----------------------------------------------------

        if len(tokens) > 2:
            return None, "", 0.0

        # ----------------------------------------------------
        # firstname.surname
        # firstname_surname
        # firstname-surname
        # ----------------------------------------------------

        if len(tokens) == 2:
            first_token = cls._ascii_token(
                tokens[0]
            )

            surname_token = cls._ascii_token(
                tokens[1]
            )

            if (
                first_token == normalized_first
                and cls._valid_surname_token(
                    surname_token
                )
            ):
                return (
                    cls._compose_name(
                        first_name,
                        surname_token,
                    ),
                    "email_exact_first_surname",
                    0.90,
                )

            # ------------------------------------------------
            # initial.surname
            # j.szulc
            # ------------------------------------------------

            if (
                len(first_token) == 1
                and first_token
                == normalized_first[0]
                and cls._valid_surname_token(
                    surname_token
                )
            ):
                return (
                    cls._compose_name(
                        first_name,
                        surname_token,
                    ),
                    "email_initial_surname",
                    0.84,
                )

            return None, "", 0.0

        # ----------------------------------------------------
        # Compact firstnamesurname.
        #
        # Useful, but weaker:
        # grzegorzszarbsko
        #
        # Potentially ambiguous:
        # piotradamklys
        #
        # Therefore REVIEW only and lower confidence.
        # ----------------------------------------------------

        compact = cls._ascii_token(
            local_part
        )

        if (
            compact.startswith(
                normalized_first
            )
            and len(compact)
            > len(normalized_first) + 2
        ):
            remainder = compact[
                len(normalized_first):
            ]

            if cls._valid_surname_token(
                remainder
            ):
                return (
                    cls._compose_name(
                        first_name,
                        remainder,
                    ),
                    "email_compact_first_surname",
                    0.72,
                )

        return None, "", 0.0

    @staticmethod
    def _valid_surname_token(
        value: str,
    ) -> bool:
        if len(value) < 3:
            return False

        if not value.isalpha():
            return False

        blocked = {
            "mail",
            "gmail",
            "email",
            "kontakt",
            "office",
            "biuro",
            "info",
            "admin",
            "bestwork",
            "prawo",
            "firma",
            "service",
            "studio",
        }

        return value not in blocked

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _compose_name(
        first_name: str,
        surname_ascii: str,
    ) -> str:
        first = (
            first_name.strip()[:1].upper()
            + first_name.strip()[1:]
        )

        surname = (
            surname_ascii[:1].upper()
            + surname_ascii[1:].lower()
        )

        return f"{first} {surname}"

    @staticmethod
    def _first_name_token(
        value: str,
    ) -> str:
        tokens = value.split()

        if not tokens:
            return ""

        return tokens[0]

    @staticmethod
    def _normalize_email(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        text = str(
            value
        ).strip().lower()

        if not EMAIL_RE.match(
            text
        ):
            return ""

        return text

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
    def _clean(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        return " ".join(
            str(value)
            .strip()
            .split()
        )

    @staticmethod
    def _ascii_token(
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
            character.lower()
            for character in without_marks
            if character.isalnum()
        )

    @classmethod
    def _normalize_person_name(
        cls,
        value: str,
    ) -> str:
        return " ".join(
            cls._ascii_token(
                token
            )
            for token in value.split()
            if token
        )

    @classmethod
    def _unique_values(
        cls,
        values: list[str],
    ) -> dict[str, str]:
        result: dict[str, str] = {}

        for value in values:
            normalized = (
                cls._normalize_person_name(
                    value
                )
            )

            if normalized:
                result.setdefault(
                    normalized,
                    value,
                )

        return result
