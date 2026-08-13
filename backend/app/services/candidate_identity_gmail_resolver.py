from __future__ import annotations

import re
import unicodedata
from typing import Any

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.services.candidate_identity_resolver import (
    IdentityEvidence,
    IdentityResolution,
)
from app.services.candidate_identity_secondary_resolver import (
    CandidateIdentitySecondaryResolver,
)


EMAIL_RE = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
    re.IGNORECASE,
)

URL_RE = re.compile(
    r"(?:https?://|www\.)",
    re.IGNORECASE,
)

PHONE_RE = re.compile(
    r"(?:\+?48[\s-]*)?"
    r"(?:\d[\s-]*){9,11}"
)

SALUTATION_LINE_RE = re.compile(
    r"^\s*"
    r"(?:dzień\s+dobry[,! ]*)?"
    r"(?:witam[,! ]*)?"
    r"(?:szanowny\s+)?"
    r"(?:panie|pani)"
    r"\s+"
    r"([A-ZĄĆĘŁŃÓŚŹŻ]"
    r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż'-]{1,30})"
    r"\b",
    re.IGNORECASE,
)


QUOTE_PREFIXES = (
    "-----original message-----",
    "----- original message -----",
    "----- wiadomość oryginalna -----",
    "----- wiadomość przekazana -----",
    "from:",
    "od:",
    "sent:",
    "wysłano:",
    "wyslano:",
    "begin forwarded message:",
)

QUOTE_CONTAINS = (
    " napisał:",
    " napisała:",
    " wrote:",
)


SIGNOFF_PREFIXES = (
    "pozdrawiam serdecznie ",
    "serdecznie pozdrawiam ",
    "z poważaniem ",
    "z powazaniem ",
    "pozdrawiam ",
    "pozdrawiam, ",
    "regards ",
    "best regards ",
    "kind regards ",
)


BLOCKED_EXACT_LINES = {
    "dzień dobry",
    "dzien dobry",
    "dobry wieczór",
    "dobry wieczor",
    "witam",
    "witam serdecznie",
    "szanowni państwo",
    "szanowni panstwo",
    "szanowny panie",
    "szanowna pani",
    "z poważaniem",
    "z powazaniem",
    "pozdrawiam",
    "pozdrawiam serdecznie",
    "serdecznie pozdrawiam",
    "miłego dnia",
    "milego dnia",
    "warmest regards",
    "best regards",
    "kind regards",
    "sign up today",
    "submit appeal",
    "google play",
    "app store",
    "contact hmi",
    "email hmi",
    "podnoszenie posadzek",
    "nadzory przeglądy",
    "nadzory przeglady",
    "oddział bydgoszcz",
    "oddzial bydgoszcz",
    "zespół facebooka",
    "zespol facebooka",
}


BLOCKED_FIRST_TOKENS = {
    "administrator",
    "architekt",
    "biuro",
    "customer",
    "dzień",
    "dzien",
    "dyrektor",
    "email",
    "facebook",
    "google",
    "hello",
    "inżynier",
    "inzynier",
    "kierownik",
    "koordynator",
    "nadzory",
    "oddział",
    "oddzial",
    "performance",
    "podnoszenie",
    "potwierdzenie",
    "prezes",
    "przedsiębiorstwo",
    "przedsiebiorstwo",
    "referent",
    "service",
    "specjalista",
    "spółdzielnia",
    "spoldzielnia",
    "support",
    "szanowni",
    "szanowny",
    "team",
    "witam",
    "zespół",
    "zespol",
}


BLOCKED_ANY_TOKENS = {
    "administrator",
    "administracyjno-techniczny",
    "budownictwa",
    "budowy",
    "compliance",
    "customer",
    "dział",
    "dzial",
    "działu",
    "dzialu",
    "facebooka",
    "marketing",
    "mieszkaniowa",
    "mieszkaniowych",
    "nieruchomości",
    "nieruchomosci",
    "nadzoru",
    "office",
    "organizacyjnego",
    "partner",
    "posadzek",
    "projektu",
    "service",
    "specialist",
    "support",
    "technicznego",
    "wspólnot",
    "wspolnot",
    "wydziału",
    "wydzialu",
    "zarządu",
    "zarzadu",
}


class CandidateIdentityGmailResolver:
    """
    Gmail Identity Layer 1.2.

    READ ONLY.

    Goals:
    - strict separation of signature names from prose,
    - understand signoff + person grammar,
    - ignore quoted history,
    - keep Polish vocative as evidence only,
    - never return AUTO_SAFE in version 1.2.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

        self.secondary = (
            CandidateIdentitySecondaryResolver(
                db
            )
        )

    def resolve(
        self,
        candidate: ClientCandidate,
    ) -> IdentityResolution:
        base = self.secondary.resolve(
            candidate
        )

        if base.status != "insufficient":
            return base

        candidate_email = self._normalize_email(
            candidate.primary_email
        )

        candidate_phone = self._normalize_phone(
            candidate.primary_phone
        )

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
                CandidateSource.created_at.asc(),
                CandidateSource.id.asc(),
            )
            .all()
        )

        if not sources:
            return base

        signature_evidence: list[
            IdentityEvidence
        ] = []

        salutation_evidence: list[
            IdentityEvidence
        ] = []

        phone_evidence: list[
            IdentityEvidence
        ] = []

        for source in sources:
            payload = source.raw_payload or {}

            full_text = self._message_text(
                payload
            )

            newest_text = (
                self._strip_quoted_history(
                    full_text
                )
            )

            sender_addresses = (
                self._header_addresses(
                    payload,
                    "from",
                )
            )

            recipient_addresses = (
                self._header_addresses(
                    payload,
                    "to",
                )
                + self._header_addresses(
                    payload,
                    "cc",
                )
            )

            candidate_is_sender = bool(
                candidate_email
                and candidate_email
                in sender_addresses
            )

            candidate_is_recipient = bool(
                candidate_email
                and candidate_email
                in recipient_addresses
            )

            if (
                candidate_phone
                and self._text_contains_phone(
                    newest_text,
                    candidate_phone,
                )
            ):
                phone_evidence.append(
                    IdentityEvidence(
                        value=(
                            candidate.primary_phone
                            or ""
                        ),
                        method=(
                            "gmail_body_phone_match"
                        ),
                        source_id=source.id,
                        source_type=(
                            source.source_type
                        ),
                    )
                )

            if (
                candidate_is_sender
                and newest_text
            ):
                for name in (
                    self._extract_signature_names(
                        newest_text
                    )
                ):
                    signature_evidence.append(
                        IdentityEvidence(
                            value=name,
                            method=(
                                "gmail_signature_name"
                            ),
                            source_id=source.id,
                            source_type=(
                                source.source_type
                            ),
                        )
                    )

            if (
                candidate_is_recipient
                and newest_text
            ):
                for vocative in (
                    self._extract_salutation_vocatives(
                        newest_text
                    )
                ):
                    salutation_evidence.append(
                        IdentityEvidence(
                            value=vocative,
                            method=(
                                "gmail_salutation_vocative"
                            ),
                            source_id=source.id,
                            source_type=(
                                source.source_type
                            ),
                        )
                    )

        unique_signatures = (
            self._unique_names(
                signature_evidence
            )
        )

        all_evidence = (
            base.evidence
            + signature_evidence
            + salutation_evidence
            + phone_evidence
        )

        # ====================================================
        # MULTIPLE DISTINCT PERSON NAMES
        # ====================================================

        if len(unique_signatures) > 1:
            return IdentityResolution(
                candidate_id=candidate.id,
                current_name=candidate.name,
                proposed_name=None,
                status="ambiguous",
                confidence=0.0,
                reason=(
                    "Multiple distinct plausible "
                    "customer-side person names remain "
                    "after Gmail signature grammar "
                    "filtering."
                ),
                evidence=all_evidence,
            )

        # ====================================================
        # ONE DISTINCT PERSON NAME
        # ====================================================

        if len(unique_signatures) == 1:
            normalized_name, full_name = next(
                iter(
                    unique_signatures.items()
                )
            )

            signature_sources = {
                evidence.source_id
                for evidence in signature_evidence
                if self._normalize_person_name(
                    evidence.value
                )
                == normalized_name
            }

            repeated = (
                len(signature_sources)
                >= 2
            )

            email_aligned = (
                self._email_matches_name(
                    candidate_email,
                    full_name,
                )
            )

            current_same = (
                self._normalize_person_name(
                    candidate.name or ""
                )
                == normalized_name
            )

            if current_same:
                return IdentityResolution(
                    candidate_id=candidate.id,
                    current_name=candidate.name,
                    proposed_name=candidate.name,
                    status="insufficient",
                    confidence=max(
                        base.confidence,
                        0.92,
                    ),
                    reason=(
                        "Gmail independently confirms "
                        "the current candidate name; "
                        "no identity-name change is "
                        "required."
                    ),
                    evidence=all_evidence,
                )

            if (
                repeated
                and email_aligned
            ):
                confidence = 0.98

                reason = (
                    "The same customer-side full name "
                    "appears in multiple Gmail messages "
                    "and aligns with the candidate email. "
                    "Still REVIEW-only in Gmail Layer 1.2."
                )

            elif email_aligned:
                confidence = 0.96

                reason = (
                    "A customer-side full name aligns "
                    "with the candidate email. "
                    "Still REVIEW-only in Gmail Layer 1.2."
                )

            elif repeated:
                confidence = 0.94

                reason = (
                    "The same customer-side full name "
                    "appears in multiple Gmail messages. "
                    "Still REVIEW-only in Gmail Layer 1.2."
                )

            else:
                confidence = 0.88

                reason = (
                    "One plausible customer-side full "
                    "name remains after Gmail signature "
                    "grammar filtering."
                )

            evidence = list(
                all_evidence
            )

            if email_aligned:
                evidence.append(
                    IdentityEvidence(
                        value=full_name,
                        method=(
                            "gmail_signature_email_alignment"
                        ),
                        source_id=0,
                        source_type="candidate_email",
                    )
                )

            return IdentityResolution(
                candidate_id=candidate.id,
                current_name=candidate.name,
                proposed_name=full_name,
                status="review",
                confidence=confidence,
                reason=reason,
                evidence=evidence,
            )

        # ====================================================
        # VOCATIVE ONLY
        # ====================================================

        if salutation_evidence:
            return IdentityResolution(
                candidate_id=candidate.id,
                current_name=candidate.name,
                proposed_name=base.proposed_name,
                status="insufficient",
                confidence=max(
                    base.confidence,
                    0.68,
                ),
                reason=(
                    "Gmail contains salutation "
                    "evidence, but Polish vocative "
                    "forms remain raw evidence only."
                ),
                evidence=all_evidence,
            )

        return IdentityResolution(
            candidate_id=base.candidate_id,
            current_name=base.current_name,
            proposed_name=base.proposed_name,
            status=base.status,
            confidence=base.confidence,
            reason=base.reason,
            evidence=all_evidence,
        )

    # ========================================================
    # BODY
    # ========================================================

    @staticmethod
    def _message_text(
        payload: dict[str, Any],
    ) -> str:
        for key in (
            "text",
            "textPlain",
            "snippet",
        ):
            value = payload.get(key)

            if value:
                return str(value)

        return ""

    # ========================================================
    # QUOTED HISTORY
    # ========================================================

    @classmethod
    def _strip_quoted_history(
        cls,
        text: str,
    ) -> str:
        if not text:
            return ""

        result: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.strip()

            lowered = line.casefold()

            if line.startswith(">"):
                break

            if any(
                lowered.startswith(prefix)
                for prefix in QUOTE_PREFIXES
            ):
                break

            if any(
                marker in lowered
                for marker in QUOTE_CONTAINS
            ):
                break

            result.append(
                raw_line
            )

        return "\n".join(
            result
        ).strip()

    # ========================================================
    # SIGNATURE EXTRACTION
    # ========================================================

    @classmethod
    def _extract_signature_names(
        cls,
        text: str,
    ) -> list[str]:
        lines = [
            cls._clean_line(line)
            for line in text.splitlines()
        ]

        lines = [
            line
            for line in lines
            if line
        ]

        if not lines:
            return []

        tail = lines[-14:]

        results: list[str] = []

        for index, line in enumerate(tail):
            normalized = (
                cls._normalize_signature_candidate(
                    line
                )
            )

            if (
                normalized
                and cls._valid_full_person_name(
                    normalized
                )
            ):
                results.append(
                    normalized
                )

            # Explicit signoff on its own line:
            #
            # Pozdrawiam
            # Jan Kowalski
            #
            if cls._is_signoff_only(
                line
            ):
                if (
                    index + 1
                    < len(tail)
                ):
                    next_line = (
                        cls._normalize_signature_candidate(
                            tail[index + 1]
                        )
                    )

                    if (
                        next_line
                        and cls._valid_full_person_name(
                            next_line
                        )
                    ):
                        results.append(
                            next_line
                        )

        return list(
            dict.fromkeys(
                results
            )
        )

    @classmethod
    def _normalize_signature_candidate(
        cls,
        value: str,
    ) -> str:
        text = " ".join(
            value.strip().split()
        )

        if not text:
            return ""

        text = cls._strip_safe_title_prefix(
            text
        )

        lowered = text.casefold()

        # ----------------------------------------------------
        # Signoff + same-line person:
        # Pozdrawiam Jan Kowalski
        # -> Jan Kowalski
        # ----------------------------------------------------

        for prefix in SIGNOFF_PREFIXES:
            prefix_cf = prefix.casefold()

            if lowered.startswith(
                prefix_cf
            ):
                text = text[
                    len(prefix):
                ].strip(
                    " ,;:-"
                )

                lowered = text.casefold()

                break

        # ----------------------------------------------------
        # Never interpret a salutation as sender signature.
        # ----------------------------------------------------

        salutation_prefixes = (
            "panie ",
            "pani ",
            "witam panie ",
            "witam pani ",
            "szanowny panie ",
            "szanowna pani ",
            "dzień dobry panie ",
            "dzień dobry pani ",
            "dzien dobry panie ",
            "dzien dobry pani ",
        )

        if any(
            lowered.startswith(prefix)
            for prefix in salutation_prefixes
        ):
            return ""

        return cls._normalize_display_name(
            text
        )

    @classmethod
    def _valid_full_person_name(
        cls,
        value: str,
    ) -> bool:
        if not value:
            return False

        if EMAIL_RE.search(value):
            return False

        if URL_RE.search(value):
            return False

        if PHONE_RE.search(value):
            return False

        if any(
            character.isdigit()
            for character in value
        ):
            return False

        lowered = value.casefold().strip()

        if lowered in BLOCKED_EXACT_LINES:
            return False

        tokens = value.split()

        if len(tokens) < 2:
            return False

        if len(tokens) > 3:
            return False

        normalized_tokens: list[str] = []

        for token in tokens:
            cleaned = token.strip(
                ".,;:()[]{}"
            )

            if not cleaned:
                return False

            # Every name component should start with an
            # uppercase character.
            if not cleaned[0].isupper():
                return False

            alpha = (
                cleaned
                .replace("-", "")
                .replace("'", "")
            )

            if len(alpha) < 2:
                return False

            if not alpha.isalpha():
                return False

            normalized_tokens.append(
                cls._ascii_token(
                    cleaned
                )
            )

        if not normalized_tokens:
            return False

        if (
            normalized_tokens[0]
            in BLOCKED_FIRST_TOKENS
        ):
            return False

        if any(
            token in BLOCKED_ANY_TOKENS
            for token in normalized_tokens
        ):
            return False

        # Two all-uppercase tokens are much more likely
        # to be an organization/unit than a person name.
        if (
            len(tokens) == 2
            and all(
                token.isupper()
                for token in tokens
            )
        ):
            return False

        return True

    @staticmethod
    def _is_signoff_only(
        value: str,
    ) -> bool:
        lowered = value.casefold().strip(
            " ,;:.-"
        )

        return lowered in {
            "pozdrawiam",
            "pozdrawiam serdecznie",
            "serdecznie pozdrawiam",
            "z poważaniem",
            "z powazaniem",
            "best regards",
            "kind regards",
            "regards",
        }

    @staticmethod
    def _strip_safe_title_prefix(
        value: str,
    ) -> str:
        text = " ".join(
            value.split()
        )

        prefixes = (
            "mgr inż. ",
            "mgr inz. ",
            "mgr inż ",
            "mgr inz ",
            "mgr. ",
            "mgr ",
            "dr inż. ",
            "dr inz. ",
            "dr inż ",
            "dr inz ",
            "dr. ",
            "dr ",
            "arch. ",
            "arch ",
            "aplikant radcowski ",
        )

        lowered = text.casefold()

        for prefix in prefixes:
            if lowered.startswith(
                prefix.casefold()
            ):
                return text[
                    len(prefix):
                ].strip()

        return text

    # ========================================================
    # SALUTATION / VOCATIVE
    # ========================================================

    @classmethod
    def _extract_salutation_vocatives(
        cls,
        text: str,
    ) -> list[str]:
        lines = [
            cls._clean_line(line)
            for line in text.splitlines()
        ]

        lines = [
            line
            for line in lines
            if line
        ][:6]

        values: list[str] = []

        for line in lines:
            match = SALUTATION_LINE_RE.search(
                line
            )

            if not match:
                continue

            value = match.group(1).strip(
                ".,;:!?()[]{}"
            )

            if value:
                values.append(value)

        return list(
            dict.fromkeys(values)
        )

    # ========================================================
    # EMAIL ALIGNMENT
    # ========================================================

    @classmethod
    def _email_matches_name(
        cls,
        email: str,
        full_name: str,
    ) -> bool:
        if not email:
            return False

        local = email.split(
            "@",
            1,
        )[0]

        local_ascii = cls._ascii_token(
            local
        )

        name_tokens = [
            cls._ascii_token(token)
            for token in full_name.split()
            if cls._ascii_token(token)
        ]

        if len(name_tokens) < 2:
            return False

        first = name_tokens[0]
        surname = name_tokens[-1]

        if not first or not surname:
            return False

        if local_ascii in {
            first + surname,
            surname + first,
        }:
            return True

        explicit_parts = [
            cls._ascii_token(part)
            for part in re.split(
                r"[._-]+",
                local,
            )
            if cls._ascii_token(part)
        ]

        if (
            first in explicit_parts
            and surname in explicit_parts
        ):
            return True

        initial = first[:1]

        if (
            len(explicit_parts) == 2
            and (
                explicit_parts
                == [
                    initial,
                    surname,
                ]
                or explicit_parts
                == [
                    surname,
                    initial,
                ]
            )
        ):
            return True

        return False

    # ========================================================
    # HEADERS
    # ========================================================

    @classmethod
    def _header_addresses(
        cls,
        payload: dict[str, Any],
        field_name: str,
    ) -> list[str]:
        field = payload.get(
            field_name
        )

        if not isinstance(
            field,
            dict,
        ):
            return []

        entries = field.get(
            "value"
        )

        if not isinstance(
            entries,
            list,
        ):
            return []

        result: list[str] = []

        for entry in entries:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            email = cls._normalize_email(
                entry.get(
                    "address"
                )
            )

            if email:
                result.append(
                    email
                )

        return list(
            dict.fromkeys(result)
        )

    # ========================================================
    # PHONE
    # ========================================================

    @classmethod
    def _text_contains_phone(
        cls,
        text: str,
        expected_phone: str,
    ) -> bool:
        if not text:
            return False

        for match in PHONE_RE.findall(
            text
        ):
            actual = cls._normalize_phone(
                match
            )

            if (
                actual
                and actual
                == expected_phone
            ):
                return True

        return False

    @staticmethod
    def _normalize_phone(
        value: Any,
    ) -> str:
        if not value:
            return ""

        digits = re.sub(
            r"\D",
            "",
            str(value),
        )

        if (
            digits.startswith("48")
            and len(digits) == 11
        ):
            digits = digits[2:]

        if len(digits) != 9:
            return ""

        return digits

    # ========================================================
    # GENERIC
    # ========================================================

    @staticmethod
    def _normalize_email(
        value: Any,
    ) -> str:
        if not value:
            return ""

        text = str(
            value
        ).strip().lower()

        if not EMAIL_RE.fullmatch(
            text
        ):
            return ""

        return text

    @staticmethod
    def _clean_line(
        value: str,
    ) -> str:
        return " ".join(
            value.strip().split()
        )

    @staticmethod
    def _normalize_display_name(
        value: str,
    ) -> str:
        return " ".join(
            token.strip(
                ".,;:()[]{}"
            )
            for token in value.split()
            if token.strip(
                ".,;:()[]{}"
            )
        )

    @classmethod
    def _normalize_person_name(
        cls,
        value: str,
    ) -> str:
        return " ".join(
            cls._ascii_token(token)
            for token in value.split()
            if cls._ascii_token(token)
        )

    @classmethod
    def _unique_names(
        cls,
        evidence: list[
            IdentityEvidence
        ],
    ) -> dict[str, str]:
        result: dict[str, str] = {}

        for item in evidence:
            normalized = (
                cls._normalize_person_name(
                    item.value
                )
            )

            if normalized:
                result.setdefault(
                    normalized,
                    item.value,
                )

        return result

    @staticmethod
    def _ascii_token(
        value: str,
    ) -> str:
        normalized = (
            unicodedata.normalize(
                "NFKD",
                value,
            )
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
