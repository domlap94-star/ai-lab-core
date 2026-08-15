from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.services.gmail_message_boundary_service import (
    GmailMessageBoundaryService,
)


EMAIL_RE = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)

LEGAL_ENTITY_RE = re.compile(
    r"(?:"
    r"\bsp\.?\s*z\.?\s*o\.?\s*o\.?\b"
    r"|\bsp\.?\s*zo\.?o\.?\b"
    r"|\bs\.?\s*a\.?\b"
    r"|\bs\.?\s*c\.?\b"
    r"|\bspółka\b"
    r"|\bspolka\b"
    r"|\bfundacja\b"
    r"|\bstowarzyszenie\b"
    r"|\bspółdzielnia\b"
    r"|\bspoldzielnia\b"
    r")",
    re.IGNORECASE,
)

PUBLIC_ENTITY_RE = re.compile(
    r"(?:"
    r"^\s*powiat\b"
    r"|^\s*starostwo\b"
    r"|^\s*urząd\b"
    r"|^\s*urzad\b"
    r"|^\s*gmina\b"
    r"|^\s*miasto\b"
    r"|^\s*województwo\b"
    r"|^\s*wojewodztwo\b"
    r"|^\s*urząd miasta\b"
    r"|^\s*urzad miasta\b"
    r"|^\s*urząd gminy\b"
    r"|^\s*urzad gminy\b"
    r")",
    re.IGNORECASE,
)

ORG_UNIT_RE = re.compile(
    r"(?:"
    r"\boddział\b"
    r"|\boddzial\b"
    r"|\bdział\b"
    r"|\bdzial\b"
    r"|\bwydział\b"
    r"|\bwydzial\b"
    r"|\bfilia\b"
    r"|\bzakład\b"
    r"|\bzaklad\b"
    r")",
    re.IGNORECASE,
)

NIP_RE = re.compile(
    r"\bNIP\s*[:\-]?\s*"
    r"([0-9][0-9\-\s]{8,16}[0-9])\b",
    re.IGNORECASE,
)

COMPANY_WORD_RE = re.compile(
    r"(?:"
    r"\binvest\b"
    r"|\bdevelopment\b"
    r"|\bconstruction\b"
    r"|\bprojekt\b"
    r"|\bbiuro rachunkowe\b"
    r"|\bcentrum budownictwa\b"
    r"|\bdomy\b"
    r"|\bnieruchomości\b"
    r"|\bnieruchomosci\b"
    r")",
    re.IGNORECASE,
)

SIGNOFFS = {
    "pozdrawiam",
    "pozdrawiam serdecznie",
    "serdecznie pozdrawiam",
    "z poważaniem",
    "z powazaniem",
    "best regards",
    "kind regards",
    "regards",
}

BODY_ENTITY_BLOCKLIST = {
    "zapytanie ofertowe",
    "oferta",
    "faktura",
    "umowa",
    "dane do faktury",
    "dzień dobry",
    "dzien dobry",
    "dobry wieczór",
    "dobry wieczor",
    "witam",
}


@dataclass(frozen=True)
class EntityEvidence:
    method: str
    value: str
    source_id: int
    source_type: str


@dataclass
class ClientEntityProjection:
    candidate_id: int
    current_name: str
    current_client_type: str

    entity_name: str | None = None
    entity_type: str = "other"

    legal_name: str | None = None

    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None

    organizational_unit: str | None = None

    tax_id: str | None = None

    confidence: float = 0.0
    status: str = "insufficient"
    reason: str = ""

    gmail_direct_messages: int = 0
    gmail_relay_messages: int = 0
    gmail_quoted_boundaries: int = 0

    evidence: list[EntityEvidence] = field(
        default_factory=list
    )


class ClientEntityProjectionService:
    """
    Client Entity Projection 1.2.

    READ ONLY.

    Main architecture:

        raw Gmail
            -> GmailMessageBoundaryService
            -> current-author content only
            -> entity/contact extraction

    Quoted history is never identity evidence for the current
    candidate.

    Explicit contact-form relay messages are not projected
    onto their technical envelope candidate. A relay candidate
    may contain many independent leads and requires a separate
    staging-repair workflow.

    No database writes.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

        self.gmail_boundary = (
            GmailMessageBoundaryService()
        )

    # ========================================================
    # PUBLIC
    # ========================================================

    def project(
        self,
        candidate: ClientCandidate,
        *,
        include_candidate_name_evidence: bool = True,
    ) -> ClientEntityProjection:
        projection = ClientEntityProjection(
            candidate_id=candidate.id,
            current_name=candidate.name,
            current_client_type=candidate.client_type,
            contact_email=self._clean(
                candidate.primary_email
            )
            or None,
            contact_phone=self._clean(
                candidate.primary_phone
            )
            or None,
            tax_id=self._normalize_nip(
                candidate.tax_id
            )
            or None,
        )

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

        entity_candidates = []
        contact_candidates = []
        unit_candidates = []
        tax_candidates = []

        for source in sources:
            payload = source.raw_payload or {}

            if (
                source.source_type
                == "google_sheets_row"
            ):
                self._consume_sheet(
                    payload=payload,
                    source=source,
                    entity_candidates=entity_candidates,
                    contact_candidates=contact_candidates,
                    unit_candidates=unit_candidates,
                    tax_candidates=tax_candidates,
                    projection=projection,
                    include_candidate_name_evidence=(
                        include_candidate_name_evidence
                    ),
                )

            elif (
                source.source_type
                == "gmail_message"
            ):
                self._consume_gmail(
                    candidate=candidate,
                    payload=payload,
                    source=source,
                    entity_candidates=entity_candidates,
                    contact_candidates=contact_candidates,
                    unit_candidates=unit_candidates,
                    tax_candidates=tax_candidates,
                    projection=projection,
                )

        self._apply_best_entity(
            projection,
            entity_candidates,
        )

        self._apply_best_contact(
            projection,
            contact_candidates,
        )

        self._apply_best_unit(
            projection,
            unit_candidates,
        )

        self._apply_best_tax(
            projection,
            tax_candidates,
        )

        self._apply_person_fallback(
            projection,
            candidate,
            include_candidate_name_evidence=(
                include_candidate_name_evidence
            ),
        )

        self._finalize(
            projection
        )

        return projection

    # ========================================================
    # GOOGLE SHEETS
    # ========================================================

    def _consume_sheet(
        self,
        *,
        payload: dict[str, Any],
        source: CandidateSource,
        entity_candidates,
        contact_candidates,
        unit_candidates,
        tax_candidates,
        projection: ClientEntityProjection,
        include_candidate_name_evidence: bool,
    ) -> None:
        first_field = self._value(
            payload,
            "IMIĘ ",
            "IMIĘ",
        )

        second_field = self._value(
            payload,
            "NAZWISKO",
        )

        sheet_email = self._value(
            payload,
            "E-MAIL",
        )

        sheet_phone = self._value(
            payload,
            "TELEFON",
        )

        # Person + organization in legacy fields.
        if (
            first_field
            and second_field
            and self._looks_person_name(
                first_field
            )
            and self._looks_entity_name(
                second_field
            )
        ):
            contact_candidates.append(
                (
                    first_field,
                    source.id,
                    source.source_type,
                    0.97,
                    "google_sheets_contact_plus_entity",
                )
            )

            entity_candidates.append(
                (
                    second_field,
                    self._classify_entity(
                        second_field
                    ),
                    source.id,
                    source.source_type,
                    0.97,
                    "google_sheets_contact_plus_entity",
                )
            )

        for value in (
            first_field,
            second_field,
        ):
            if not value:
                continue

            split = self._split_org_person(
                value
            )

            if split is None:
                continue

            entity_name, contact_name = split

            entity_candidates.append(
                (
                    entity_name,
                    self._classify_entity(
                        entity_name
                    ),
                    source.id,
                    source.source_type,
                    0.95,
                    "google_sheets_combined_entity_contact",
                )
            )

            contact_candidates.append(
                (
                    contact_name,
                    source.id,
                    source.source_type,
                    0.95,
                    "google_sheets_combined_entity_contact",
                )
            )

        if (
            first_field
            and second_field
            and not self._looks_entity_name(
                second_field
            )
        ):
            combined_person = self._clean(
                f"{first_field} {second_field}"
            )

            if self._looks_person_name(
                combined_person
            ):
                contact_candidates.append(
                    (
                        combined_person,
                        source.id,
                        source.source_type,
                        0.90,
                        "google_sheets_person",
                    )
                )

        elif (
            first_field
            and self._looks_person_name(
                first_field
            )
        ):
            contact_candidates.append(
                (
                    first_field,
                    source.id,
                    source.source_type,
                    0.82,
                    "google_sheets_person_partial",
                )
            )

        current_name = (
            self._clean(projection.current_name)
            if include_candidate_name_evidence
            else ""
        )

        current_split = self._split_org_person(
            current_name
        )

        if current_split is not None:
            entity_name, contact_name = (
                current_split
            )

            entity_candidates.append(
                (
                    entity_name,
                    self._classify_entity(
                        entity_name
                    ),
                    source.id,
                    source.source_type,
                    0.93,
                    "candidate_name_combined_entity_contact",
                )
            )

            contact_candidates.append(
                (
                    contact_name,
                    source.id,
                    source.source_type,
                    0.93,
                    "candidate_name_combined_entity_contact",
                )
            )

        elif self._looks_entity_name(
            current_name
        ):
            entity_candidates.append(
                (
                    current_name,
                    self._classify_entity(
                        current_name
                    ),
                    source.id,
                    source.source_type,
                    0.91,
                    "candidate_name_entity",
                )
            )

        if (
            sheet_email
            and EMAIL_RE.match(
                sheet_email
            )
            and not projection.contact_email
        ):
            projection.contact_email = (
                sheet_email.casefold()
            )

        if (
            sheet_phone
            and not projection.contact_phone
        ):
            projection.contact_phone = (
                sheet_phone
            )

        for key in (
            "NIP",
            "nip",
            "Tax ID",
            "tax_id",
        ):
            nip = self._normalize_nip(
                self._value(
                    payload,
                    key,
                )
            )

            if not nip:
                continue

            tax_candidates.append(
                (
                    nip,
                    source.id,
                    source.source_type,
                    0.99,
                    "google_sheets_tax_id",
                )
            )

    # ========================================================
    # GMAIL
    # ========================================================

    def _consume_gmail(
        self,
        *,
        candidate: ClientCandidate,
        payload: dict[str, Any],
        source: CandidateSource,
        entity_candidates,
        contact_candidates,
        unit_candidates,
        tax_candidates,
        projection: ClientEntityProjection,
    ) -> None:
        raw_text = self._message_text(
            payload
        )

        boundary = (
            self.gmail_boundary.parse(
                raw_text
            )
        )

        if boundary.boundary_method:
            projection.gmail_quoted_boundaries += 1

        # ----------------------------------------------------
        # Relay messages describe one or more external leads,
        # not the technical sender candidate.
        #
        # Do not collapse their submitted identities onto
        # candidate 3095 / 3344.
        # ----------------------------------------------------

        if boundary.relay_payload is not None:
            projection.gmail_relay_messages += 1
            return

        candidate_email = self._normalize_email(
            candidate.primary_email
        )

        sender = self._header_identity(
            payload,
            "from",
        )

        if sender is None:
            return

        sender_email, display_name = sender

        if not (
            candidate_email
            and sender_email
            and candidate_email
            == sender_email
        ):
            return

        projection.gmail_direct_messages += 1

        self._consume_display_name(
            display_name=display_name,
            source=source,
            entity_candidates=entity_candidates,
            contact_candidates=contact_candidates,
        )

        # ====================================================
        # CRITICAL 1.2 CHANGE
        #
        # All identity extraction uses current-author content.
        # Quoted history is unavailable to the resolver.
        # ====================================================

        current_text = (
            boundary.current_content
        )

        if not current_text:
            return

        lines = [
            self._clean(line)
            for line
            in current_text.splitlines()
            if self._clean(line)
        ]

        for line in lines:
            if self._looks_organizational_unit_line(
                line
            ):
                unit_candidates.append(
                    (
                        line,
                        source.id,
                        source.source_type,
                        0.86,
                        "gmail_current_org_unit",
                    )
                )

            if self._looks_entity_line(
                line
            ):
                entity_candidates.append(
                    (
                        line,
                        self._classify_entity(
                            line
                        ),
                        source.id,
                        source.source_type,
                        0.88,
                        "gmail_current_entity_line",
                    )
                )

            nip_match = NIP_RE.search(
                line
            )

            if nip_match:
                nip = self._normalize_nip(
                    nip_match.group(1)
                )

                if nip:
                    tax_candidates.append(
                        (
                            nip,
                            source.id,
                            source.source_type,
                            0.99,
                            "gmail_current_tax_id",
                        )
                    )

        tail = lines[-14:]

        for index, line in enumerate(
            tail
        ):
            normalized = (
                line.casefold()
                .strip(
                    " ,;:.-"
                )
            )

            if normalized not in SIGNOFFS:
                continue

            if (
                index + 1
                >= len(tail)
            ):
                continue

            next_line = tail[
                index + 1
            ]

            if self._looks_person_name(
                next_line
            ):
                contact_candidates.append(
                    (
                        next_line,
                        source.id,
                        source.source_type,
                        0.92,
                        "gmail_current_signature",
                    )
                )

    # ========================================================
    # DISPLAY NAME
    # ========================================================

    def _consume_display_name(
        self,
        *,
        display_name: str,
        source: CandidateSource,
        entity_candidates,
        contact_candidates,
    ) -> None:
        display_name = self._clean(
            display_name
        )

        if not display_name:
            return

        if " - " in display_name:
            left, right = (
                part.strip()
                for part
                in display_name.split(
                    " - ",
                    1,
                )
            )

            if (
                self._looks_person_name(
                    left
                )
                and self._looks_entity_name(
                    right
                )
            ):
                contact_candidates.append(
                    (
                        left,
                        source.id,
                        source.source_type,
                        0.98,
                        "gmail_sender_person_entity",
                    )
                )

                entity_candidates.append(
                    (
                        right,
                        self._classify_entity(
                            right
                        ),
                        source.id,
                        source.source_type,
                        0.98,
                        "gmail_sender_person_entity",
                    )
                )

                return

        if " / " in display_name:
            left, right = (
                part.strip()
                for part
                in display_name.split(
                    " / ",
                    1,
                )
            )

            if (
                self._looks_entity_name(
                    left
                )
                and self._looks_person_name(
                    right
                )
            ):
                entity_candidates.append(
                    (
                        left,
                        self._classify_entity(
                            left
                        ),
                        source.id,
                        source.source_type,
                        0.98,
                        "gmail_sender_entity_person",
                    )
                )

                contact_candidates.append(
                    (
                        right,
                        source.id,
                        source.source_type,
                        0.98,
                        "gmail_sender_entity_person",
                    )
                )

                return

        if self._looks_entity_name(
            display_name
        ):
            entity_candidates.append(
                (
                    display_name,
                    self._classify_entity(
                        display_name
                    ),
                    source.id,
                    source.source_type,
                    0.94,
                    "gmail_sender_entity",
                )
            )

            return

        if self._looks_person_name(
            display_name
        ):
            contact_candidates.append(
                (
                    display_name,
                    source.id,
                    source.source_type,
                    0.94,
                    "gmail_sender_contact",
                )
            )

    # ========================================================
    # ENTITY / CONTACT PARSING
    # ========================================================

    @classmethod
    def _classify_entity(
        cls,
        value: str,
    ) -> str:
        value = cls._clean(
            value
        )

        if PUBLIC_ENTITY_RE.search(
            value
        ):
            return "institution"

        if cls._looks_entity_name(
            value
        ):
            return "company"

        return "other"

    @classmethod
    def _looks_entity_name(
        cls,
        value: str,
    ) -> bool:
        value = cls._clean(
            value
        )

        if not value:
            return False

        if EMAIL_RE.match(
            value
        ):
            return False

        if len(value) > 120:
            return False

        if PUBLIC_ENTITY_RE.search(
            value
        ):
            return True

        if LEGAL_ENTITY_RE.search(
            value
        ):
            return True

        if COMPANY_WORD_RE.search(
            value
        ):
            if len(
                value.split()
            ) <= 8:
                return True

        tokens = value.split()

        if (
            1 <= len(tokens) <= 4
            and len(value) >= 4
            and all(
                cls._upper_brand_token(
                    token
                )
                for token in tokens
            )
        ):
            return True

        return False

    @classmethod
    def _looks_entity_line(
        cls,
        value: str,
    ) -> bool:
        value = cls._clean(
            value
        )

        if not value:
            return False

        if len(value) > 120:
            return False

        lowered = value.casefold()

        if lowered in BODY_ENTITY_BLOCKLIST:
            return False

        blocked_prefixes = (
            "dzień dobry",
            "dzien dobry",
            "witam ",
            "proszę ",
            "prosze ",
            "informacje ",
            "lokalizacja:",
            "w nawiązaniu ",
            "w nawiazaniu ",
            "zgodnie z ",
            "sąd rejonowy ",
            "sad rejonowy ",
            "dane do ",
        )

        if lowered.startswith(
            blocked_prefixes
        ):
            return False

        if any(
            marker in lowered
            for marker in (
                "http://",
                "https://",
                "mailto:",
                "<http",
            )
        ):
            return False

        if value.count(".") >= 3:
            return False

        if value.count(",") >= 4:
            return False

        if len(
            value.split()
        ) > 12:
            return False

        return cls._looks_entity_name(
            value
        )

    @classmethod
    def _looks_organizational_unit_line(
        cls,
        value: str,
    ) -> bool:
        value = cls._clean(
            value
        )

        if not value:
            return False

        if len(value) > 100:
            return False

        tokens = value.split()

        if not (
            2 <= len(tokens) <= 8
        ):
            return False

        lowered = value.casefold()

        blocked = (
            "sąd rejonowy",
            "sad rejonowy",
            "krs",
            "regon",
            "nip",
            "rejestr",
        )

        if any(
            fragment in lowered
            for fragment in blocked
        ):
            return False

        return bool(
            ORG_UNIT_RE.search(
                value
            )
        )

    @classmethod
    def _looks_person_name(
        cls,
        value: str,
    ) -> bool:
        value = cls._clean(
            value
        )

        if not value:
            return False

        if EMAIL_RE.match(
            value
        ):
            return False

        if cls._looks_entity_name(
            value
        ):
            return False

        if ORG_UNIT_RE.search(
            value
        ):
            return False

        if any(
            character.isdigit()
            for character in value
        ):
            return False

        tokens = value.split()

        if not (
            2 <= len(tokens) <= 4
        ):
            return False

        blocked_words = {
            "dzień",
            "dzien",
            "dobry",
            "witam",
            "pozdrawiam",
            "oddział",
            "oddzial",
            "dział",
            "dzial",
            "wydział",
            "wydzial",
            "podnoszenie",
            "posadzek",
            "zapytanie",
            "ofertowe",
        }

        for token in tokens:
            cleaned = token.strip(
                ".,;:()[]{}"
            )

            alpha = (
                cleaned
                .replace("-", "")
                .replace("'", "")
            )

            if (
                len(alpha) < 2
                or not alpha.isalpha()
            ):
                return False

            if (
                alpha.casefold()
                in blocked_words
            ):
                return False

        return True

    @classmethod
    def _split_org_person(
        cls,
        value: str,
    ) -> tuple[str, str] | None:
        value = cls._clean(
            value
        )

        if not value:
            return None

        if " / " in value:
            left, right = (
                part.strip()
                for part
                in value.split(
                    " / ",
                    1,
                )
            )

            if (
                cls._looks_entity_name(
                    left
                )
                and cls._looks_person_name(
                    right
                )
            ):
                return (
                    left,
                    right,
                )

        if " - " in value:
            left, right = (
                part.strip()
                for part
                in value.split(
                    " - ",
                    1,
                )
            )

            if (
                cls._looks_person_name(
                    left
                )
                and cls._looks_entity_name(
                    right
                )
            ):
                return (
                    right,
                    left,
                )

        if ", " in value:
            left, right = (
                part.strip()
                for part
                in value.split(
                    ", ",
                    1,
                )
            )

            if (
                cls._looks_entity_name(
                    left
                )
                and cls._looks_person_name(
                    right
                )
            ):
                return (
                    left,
                    right,
                )

        return None

    # ========================================================
    # APPLY BEST
    # ========================================================

    def _apply_best_entity(
        self,
        projection,
        candidates,
    ) -> None:
        best = self._best_ranked(
            candidates,
            score_index=4,
        )

        if best is None:
            return

        (
            value,
            entity_type,
            source_id,
            source_type,
            score,
            method,
        ) = best

        projection.entity_name = value
        projection.entity_type = entity_type

        if (
            entity_type == "company"
            and LEGAL_ENTITY_RE.search(
                value
            )
        ):
            projection.legal_name = value

        projection.confidence = max(
            projection.confidence,
            score,
        )

        projection.evidence.append(
            EntityEvidence(
                method=method,
                value=value,
                source_id=source_id,
                source_type=source_type,
            )
        )

    def _apply_best_contact(
        self,
        projection,
        candidates,
    ) -> None:
        best = self._best_ranked(
            candidates,
            score_index=3,
        )

        if best is None:
            return

        (
            value,
            source_id,
            source_type,
            score,
            method,
        ) = best

        projection.contact_name = value

        projection.confidence = max(
            projection.confidence,
            score,
        )

        projection.evidence.append(
            EntityEvidence(
                method=method,
                value=value,
                source_id=source_id,
                source_type=source_type,
            )
        )

    def _apply_best_unit(
        self,
        projection,
        candidates,
    ) -> None:
        best = self._best_ranked(
            candidates,
            score_index=3,
        )

        if best is None:
            return

        (
            value,
            source_id,
            source_type,
            score,
            method,
        ) = best

        projection.organizational_unit = value

        projection.confidence = max(
            projection.confidence,
            score,
        )

        projection.evidence.append(
            EntityEvidence(
                method=method,
                value=value,
                source_id=source_id,
                source_type=source_type,
            )
        )

    def _apply_best_tax(
        self,
        projection,
        candidates,
    ) -> None:
        best = self._best_ranked(
            candidates,
            score_index=3,
        )

        if best is None:
            return

        (
            value,
            source_id,
            source_type,
            score,
            method,
        ) = best

        projection.tax_id = value

        projection.confidence = max(
            projection.confidence,
            score,
        )

        projection.evidence.append(
            EntityEvidence(
                method=method,
                value=value,
                source_id=source_id,
                source_type=source_type,
            )
        )

    def _apply_person_fallback(
        self,
        projection,
        candidate,
        *,
        include_candidate_name_evidence: bool = True,
    ) -> None:
        if projection.entity_name:
            return

        if projection.contact_name:
            projection.entity_name = (
                projection.contact_name
            )
            projection.entity_type = "person"
            return

        # Do not turn a known relay container into a person
        # merely because its historical candidate.name looks
        # like a personal name.
        if (
            projection.gmail_relay_messages > 0
            and projection.gmail_direct_messages == 0
        ):
            return

        if not include_candidate_name_evidence:
            return

        current_name = self._clean(
            candidate.name
        )

        if self._looks_person_name(
            current_name
        ):
            projection.entity_name = current_name
            projection.entity_type = "person"

    @staticmethod
    def _best_ranked(
        values,
        *,
        score_index: int,
    ):
        if not values:
            return None

        grouped = {}

        for item in values:
            normalized = (
                ClientEntityProjectionService
                ._normalize_identity(
                    item[0]
                )
            )

            if not normalized:
                continue

            grouped.setdefault(
                normalized,
                [],
            ).append(item)

        ranked = []

        for _, items in grouped.items():
            best_item = sorted(
                items,
                key=lambda item: (
                    -item[score_index],
                    -len(str(item[0])),
                ),
            )[0]

            ranked.append(
                best_item
            )

        ranked.sort(
            key=lambda item: (
                -item[score_index],
                -len(str(item[0])),
                str(item[0]).casefold(),
            )
        )

        return ranked[0]

    # ========================================================
    # FINALIZE
    # ========================================================

    @staticmethod
    def _finalize(
        projection,
    ) -> None:
        if (
            projection.gmail_relay_messages > 0
            and projection.entity_name is None
        ):
            projection.status = (
                "relay_container"
            )

            projection.reason = (
                "Candidate contains explicit contact-form "
                "relay messages representing independent "
                "external leads. It must not be promoted "
                "as a single client."
            )

            return

        if projection.entity_name:
            projection.status = "review"

            if (
                projection.entity_type
                in (
                    "company",
                    "institution",
                )
                and projection.contact_name
            ):
                projection.reason = (
                    "A client entity and a separate contact "
                    "person were identified from preserved "
                    "current-author evidence."
                )

            elif (
                projection.entity_type
                in (
                    "company",
                    "institution",
                )
            ):
                projection.reason = (
                    "A client organization or institution "
                    "was identified from preserved "
                    "current-author evidence."
                )

            else:
                projection.reason = (
                    "A plausible client identity was "
                    "identified from preserved source "
                    "evidence."
                )

            return

        projection.status = "insufficient"

        projection.reason = (
            "No sufficiently reliable client identity "
            "was established."
        )

    # ========================================================
    # HELPERS
    # ========================================================

    @classmethod
    def _header_identity(
        cls,
        payload,
        field_name,
    ):
        field = payload.get(
            field_name
        )

        if not isinstance(
            field,
            dict,
        ):
            return None

        values = field.get(
            "value"
        )

        if not isinstance(
            values,
            list,
        ):
            return None

        for item in values:
            if not isinstance(
                item,
                dict,
            ):
                continue

            address = cls._normalize_email(
                item.get("address")
            )

            name = cls._clean(
                item.get("name")
            )

            if address:
                return (
                    address,
                    name,
                )

        return None

    @staticmethod
    def _message_text(
        payload,
    ):
        for key in (
            "text",
            "textPlain",
            "snippet",
        ):
            value = payload.get(
                key
            )

            if value:
                return str(value)

        return ""

    @staticmethod
    def _value(
        payload,
        *keys,
    ):
        for key in keys:
            if key not in payload:
                continue

            value = (
                ClientEntityProjectionService
                ._clean(
                    payload.get(key)
                )
            )

            if value:
                return value

        return ""

    @staticmethod
    def _clean(
        value,
    ):
        if value is None:
            return ""

        return " ".join(
            str(value).strip().split()
        )

    @staticmethod
    def _normalize_email(
        value,
    ):
        if not value:
            return ""

        text = (
            str(value)
            .strip()
            .casefold()
        )

        if not EMAIL_RE.match(
            text
        ):
            return ""

        return text

    @staticmethod
    def _normalize_nip(
        value,
    ):
        if not value:
            return ""

        digits = re.sub(
            r"\D",
            "",
            str(value),
        )

        if len(digits) != 10:
            return ""

        return digits

    @staticmethod
    def _normalize_identity(
        value,
    ):
        if not value:
            return ""

        return " ".join(
            str(value)
            .casefold()
            .strip()
            .split()
        )

    @staticmethod
    def _upper_brand_token(
        value,
    ):
        token = value.strip(
            ".,;:()[]{}-/"
        )

        if not token:
            return False

        letters = [
            character
            for character in token
            if character.isalpha()
        ]

        if not letters:
            return False

        return all(
            character.isupper()
            for character in letters
        )
