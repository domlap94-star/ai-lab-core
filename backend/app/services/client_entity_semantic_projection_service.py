from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.services.client_entity_projection_policy_service import (
    ClientEntityProjectionPolicyService,
)
from app.services.gmail_message_boundary_service import (
    GmailMessageBoundaryService,
)


EMAIL_RE = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    re.IGNORECASE,
)

PHONE_RE = re.compile(
    r"(?:\+?48[\s./-]*)?"
    r"(?:\d[\s./-]*){9}"
)

NIP_RE = re.compile(
    r"\bNIP\s*[:\-]?\s*"
    r"([0-9][0-9\s\-]{8,20}[0-9])",
    re.IGNORECASE,
)

LEGAL_ENTITY_RE = re.compile(
    r"(?:"
    r"\bsp\.?\s*z\.?\s*o\.?\s*o\.?\b"
    r"|\bspółka\s+z\s+o\.?\s*o\.?\b"
    r"|\bspolka\s+z\s+o\.?\s*o\.?\b"
    r"|\bs\.?\s*a\.?\b"
    r"|\bs\.?\s*c\.?\b"
    r"|\bsp\.?\s*k\.?\b"
    r"|\bspółka\s+komandytowa\b"
    r"|\bspolka\s+komandytowa\b"
    r"|\bfundacja\b"
    r"|\bstowarzyszenie\b"
    r")",
    re.IGNORECASE,
)

PUBLIC_ENTITY_RE = re.compile(
    r"(?:"
    r"\burząd\b"
    r"|\burzad\b"
    r"|\bstarostwo\b"
    r"|\bpowiat\b"
    r"|\bgmina\b"
    r")",
    re.IGNORECASE,
)

PUBLIC_ENTITY_NAME_RE = re.compile(
    r"^(?:"
    r"urząd\b"
    r"|urzad\b"
    r"|starostwo\b"
    r"|powiat\b"
    r"|gmina\b"
    r")",
    re.IGNORECASE,
)

PERSON_ORG_HINT_RE = re.compile(
    r"(?:"
    r"\bsp\.?\s*z\.?\s*o\.?\s*o\.?\b"
    r"|\bs\.?\s*a\.?\b"
    r"|\bmeble\b"
    r"|\bpolska\b"
    r"|\bagencja\b"
    r"|\bstudio\b"
    r"|\bprojektowanie\b"
    r"|\bkonstrukcji\b"
    r"|\bbudowlanych\b"
    r"|\bzespół\b"
    r"|\bzespol\b"
    r"|\bservices\b"
    r"|\bindustry\b"
    r"|\bcompany\b"
    r")",
    re.IGNORECASE,
)

COMPANY_MARKER_RE = re.compile(
    r"(?:"
    r"\bbuild\b"
    r"|\bbud\b"
    r"|\binvest\b"
    r"|\bconstruction\b"
    r"|\bgroup\b"
    r"|\bbiuro\b"
    r"|\bprzedsiębiorstwo\b"
    r"|\bprzedsiebiorstwo\b"
    r"|\bkorporacja\b"
    r"|\barcelormittal\b"
    r")",
    re.IGNORECASE,
)

ROLE_RE = re.compile(
    r"(?:"
    r"\bdyrektor\b"
    r"|\bkierownik\b"
    r"|\bkoordynator\b"
    r"|\bkosztorysant\b"
    r"|\bprezes\b"
    r"|\bsekretarz\b"
    r"|\bspecjalista\b"
    r"|\badwokat\b"
    r"|\bmanager\b"
    r"|\bmenedżer\b"
    r"|\bmenedzer\b"
    r")",
    re.IGNORECASE,
)

TRUE_UNIT_RE = re.compile(
    r"^(?:"
    r"oddział\b"
    r"|oddzial\b"
    r"|wydział\b"
    r"|wydzial\b"
    r"|dział\b"
    r"|dzial\b"
    r"|departament\b"
    r"|filia\b"
    r")",
    re.IGNORECASE,
)

COURT_UNIT_RE = re.compile(
    r"(?:"
    r"\bwydział\b.*\bgospodarczy\b"
    r"|\bwydzial\b.*\bgospodarczy\b"
    r")",
    re.IGNORECASE,
)

COURT_CONTEXT_RE = re.compile(
    r"(?:"
    r"sąd rejonowy"
    r"|sad rejonowy"
    r"|\bkrs\b"
    r"|krajowego rejestru sądowego"
    r"|krajowego rejestru sadowego"
    r")",
    re.IGNORECASE,
)

TITLE_PERSON_RE = re.compile(
    r"^(?:"
    r"(?:mgr|inż|inz|arch|dr|prof)"
    r"[.\s]+"
    r")+"
    r"(.+)$",
    re.IGNORECASE,
)

EXPLICIT_CONTACT_RE = re.compile(
    r"(?:telefon\s+kontaktowy|kontakt)"
    r"\s*[-:]\s*"
    r"([A-ZĄĆĘŁŃÓŚŹŻ][^\d,\n]{2,60}?)"
    r"\s+"
    r"((?:\+?48[\s./-]*)?(?:\d[\s./-]*){9})",
    re.IGNORECASE,
)

BAD_CONTACT_EXACT = {
    "z poważaniem",
    "z powazaniem",
    "z wyrazami szacunku",
    "pozdrawiam",
    "serdecznie pozdrawiam",
    "do zobaczenia",
    "tel",
    "tel.",
    "biuro",
    "firma",
}

BAD_CONTACT_FRAGMENTS = (
    "napisał(a):",
    "napisal(a):",
    "napisał:",
    "napisal:",
    "mailto:",
    "logo description",
    "automatically generated",
    "zawiera wirus",
    "web:",
)

BODY_NOISE_ENTITY_EXACT = {
    "zapytanie ofertowe",
    "lokalizacja:",
    "opinia techniczna",
    "kierownik projektu",
    "dział techniczny",
    "dzial techniczny",
    "attention:",
    "uwaga:",
    "rodo:",
    "[logo]",
}

SIGNATURE_EVIDENCE_BLOCK_RE = re.compile(
    r"(?:"
    r"https?://"
    r"|mailto:"
    r"|\bcid:"
    r"|^\s*e-?mail\s*:"
    r"|^\s*www\."
    r"|^\s*\[logo\b"
    r"|logo description"
    r"|automatically generated"
    r"|polityka\s+prywatno"
    r"|ochrona-danych"
    r")",
    re.IGNORECASE,
)

NARRATIVE_MARKERS = (
    "wszelkie inne informacje",
    "informacje zawarte",
    "niniejszej wiadomości",
    "niniejszej wiadomosci",
    "administratorem",
    "spółka zarejestrowana przez sąd",
    "spolka zarejestrowana przez sad",
    "firma ze szczecina",
    "spółdzielnia wykonała",
    "spoldzielnia wykonala",
    "budynek znajduje się",
    "budynek znajduje sie",
    "wykonania iniekcji",
    "znajduje się przy ulicy",
    "znajduje sie przy ulicy",
    "ten mail może zawierać",
    "ten mail moze zawierac",
)


@dataclass(frozen=True)
class SemanticContact:
    name: str
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    source_ids: tuple[int, ...] = ()
    confidence: float = 0.0


@dataclass(frozen=True)
class SemanticEntityEvidence:
    name: str
    entity_type: str
    method: str
    source_id: int
    confidence: float


@dataclass
class ClientEntitySemanticProjection:
    candidate_id: int

    entity_name: str | None
    entity_type: str
    legal_name: str | None
    tax_id: str | None

    contacts: list[SemanticContact] = field(
        default_factory=list
    )

    organizational_units: list[str] = field(
        default_factory=list
    )

    entity_evidence: list[SemanticEntityEvidence] = field(
        default_factory=list
    )

    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    organizational_unit: str | None = None

    status: str = "insufficient"
    reason: str = ""

    base_projection: object | None = None


class ClientEntitySemanticProjectionService:
    """
    Client Entity Projection 1.4.6.

    READ ONLY.

    Entity identity is provenance-ranked.

    Strong evidence:
    - legal organization in signature,
    - public institution in signature,
    - structured Sheets organization,
    - sender display person + organization.

    Arbitrary message-body prose is not entity evidence.

    No database writes.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

        self.base_service = (
            ClientEntityProjectionPolicyService(
                db
            )
        )

        self.gmail_boundary = (
            GmailMessageBoundaryService()
        )

    def project(
        self,
        candidate: ClientCandidate,
        *,
        include_candidate_name_evidence: bool = True,
    ) -> ClientEntitySemanticProjection:
        base = self.base_service.project(
            candidate,
            include_candidate_name_evidence=(
                include_candidate_name_evidence
            ),
        )

        result = ClientEntitySemanticProjection(
            candidate_id=candidate.id,
            entity_name=None,
            entity_type="other",
            legal_name=None,
            tax_id=base.tax_id,
            contact_name=base.contact_name,
            contact_email=base.contact_email,
            contact_phone=base.contact_phone,
            organizational_unit=base.organizational_unit,
            status=base.status,
            reason=base.reason,
            base_projection=base,
        )

        if base.status in {
            "first_party_internal",
            "relay_container",
        }:
            result.entity_name = base.entity_name
            result.entity_type = base.entity_type
            result.legal_name = base.legal_name
            return result

        sources = (
            self.db.query(CandidateSource)
            .filter(
                CandidateSource.candidate_id == candidate.id,
                CandidateSource.deleted_at.is_(None),
            )
            .order_by(
                CandidateSource.created_at.asc(),
                CandidateSource.id.asc(),
            )
            .all()
        )

        contact_candidates = []
        entity_candidates = []
        unit_candidates = []

        candidate_email = self._normalize_email(
            candidate.primary_email
        )

        for source in sources:
            payload = source.raw_payload or {}

            if source.source_type == "google_sheets_row":
                self._consume_sheet(
                    payload=payload,
                    source=source,
                    contact_candidates=contact_candidates,
                    entity_candidates=entity_candidates,
                )

            elif source.source_type == "gmail_message":
                self._consume_gmail(
                    candidate_email=candidate_email,
                    payload=payload,
                    source=source,
                    contact_candidates=contact_candidates,
                    entity_candidates=entity_candidates,
                    unit_candidates=unit_candidates,
                )

        base_entity = (
            self._sanitize_base_entity(base.entity_name)
            if include_candidate_name_evidence
            else ""
        )

        if base_entity:
            entity_candidates.append(
                SemanticEntityEvidence(
                    name=base_entity,
                    entity_type=base.entity_type,
                    method="base_fallback",
                    source_id=0,
                    confidence=0.70,
                )
            )

        contacts = self._dedupe_contacts(
            contact_candidates
        )

        units = self._dedupe_units(
            unit_candidates
        )

        best_entity = self._best_entity(
            entity_candidates
        )

        if best_entity is not None:
            result.entity_name = (
                best_entity.name
            )

            result.entity_type = (
                best_entity.entity_type
            )

            if LEGAL_ENTITY_RE.search(
                best_entity.name
            ):
                result.legal_name = (
                    best_entity.name
                )

        elif contacts:
            # Person fallback remains valid when no organization
            # has stronger evidence.
            result.entity_name = contacts[0].name
            result.entity_type = "person"

            for source_id in contacts[0].source_ids:
                entity_candidates.append(
                    SemanticEntityEvidence(
                        name=contacts[0].name,
                        entity_type="person",
                        method="person_contact_fallback",
                        source_id=source_id,
                        confidence=contacts[0].confidence,
                    )
                )

        result.entity_evidence = (
            sorted(
                entity_candidates,
                key=lambda item: (
                    -item.confidence,
                    self._normalize_identity(
                        item.name
                    ),
                ),
            )
        )

        contacts = [
            contact
            for contact in contacts
            if not self._contact_overlaps_entity(
                contact.name,
                result.entity_name,
            )
        ]

        result.contacts = contacts
        result.organizational_units = units

        if contacts:
            primary = contacts[0]

            result.contact_name = primary.name

            if primary.email:
                result.contact_email = primary.email

            if primary.phone:
                result.contact_phone = primary.phone

        else:
            result.contact_name = None

        if units:
            result.organizational_unit = units[0]

        elif (
            result.organizational_unit
            and self._looks_court_unit(
                result.organizational_unit
            )
        ):
            result.organizational_unit = None

        if (
            result.entity_type
            in {
                "company",
                "institution",
            }
            and contacts
        ):
            result.reason = (
                "A client organization and one or more "
                "separate contact persons were identified "
                "from provenance-ranked source evidence."
            )

        elif result.entity_name:
            result.status = "review"

        else:
            result.status = "insufficient"

        return result

    # ========================================================
    # GOOGLE SHEETS
    # ========================================================

    def _consume_sheet(
        self,
        *,
        payload,
        source,
        contact_candidates,
        entity_candidates,
    ) -> None:
        first = self._value(
            payload,
            "IMIĘ ",
            "IMIĘ",
            "IMI─ś ",
            "IMI─ś",
        )

        second = self._value(
            payload,
            "NAZWISKO",
        )

        email = self._normalize_email(
            self._value(
                payload,
                "E-MAIL",
            )
        )

        phone = self._clean(
            self._value(
                payload,
                "TELEFON",
            )
        )

        combined = self._clean(
            f"{first} {second}"
        )

        if self._looks_person_name(
            combined
        ):
            contact_candidates.append(
                SemanticContact(
                    name=combined,
                    email=email or None,
                    phone=phone or None,
                    source_ids=(source.id,),
                    confidence=0.94,
                )
            )

        if (
            second
            and self._looks_entity_name(
                second
            )
        ):
            entity_name = self._clean_entity(
                second
            )

            entity_candidates.append(
                SemanticEntityEvidence(
                    name=entity_name,
                    entity_type=self._classify_entity(
                        entity_name
                    ),
                    method="sheet_entity",
                    source_id=source.id,
                    confidence=0.97,
                )
            )

    # ========================================================
    # GMAIL
    # ========================================================

    def _consume_gmail(
        self,
        *,
        candidate_email,
        payload,
        source,
        contact_candidates,
        entity_candidates,
        unit_candidates,
    ) -> None:
        sender_email, sender_name = (
            self._header_identity(
                payload,
                "from",
            )
        )

        if (
            not candidate_email
            or sender_email != candidate_email
        ):
            return

        boundary = self.gmail_boundary.parse(
            self._message_text(
                payload
            )
        )

        if boundary.relay_payload:
            return

        current = boundary.current_content

        if not current:
            return

        lines = [
            self._clean(line)
            for line in current.splitlines()
            if self._clean(line)
        ]

        explicit = EXPLICIT_CONTACT_RE.search(
            current
        )

        if explicit:
            name = self._sanitize_contact_name(
                explicit.group(1)
            )

            phone = self._clean_phone(
                explicit.group(2)
            )

            if self._looks_person_name(
                name
            ):
                contact_candidates.append(
                    SemanticContact(
                        name=name,
                        phone=phone or None,
                        source_ids=(source.id,),
                        confidence=0.99,
                    )
                )

        signature_contact = (
            self._extract_signature_contact(
                lines=lines,
                candidate_email=candidate_email,
                source_id=source.id,
            )
        )

        if signature_contact is not None:
            contact_candidates.append(
                signature_contact
            )

        display_split = (
            self._split_person_entity_display(
                sender_name
            )
        )

        if display_split is not None:
            person_name, entity_name = (
                display_split
            )

            contact_candidates.append(
                SemanticContact(
                    name=person_name,
                    email=candidate_email,
                    source_ids=(source.id,),
                    confidence=0.94,
                )
            )

            entity_candidates.append(
                SemanticEntityEvidence(
                    name=entity_name,
                    entity_type=self._classify_entity(
                        entity_name
                    ),
                    method="sender_display_entity",
                    source_id=source.id,
                    confidence=0.95,
                )
            )

        else:
            clean_sender = (
                self._sanitize_contact_name(
                    sender_name
                )
            )

            if self._looks_person_name(
                clean_sender
            ):
                contact_candidates.append(
                    SemanticContact(
                        name=clean_sender,
                        email=candidate_email,
                        source_ids=(source.id,),
                        confidence=0.90,
                    )
                )

        for evidence in (
            self._extract_signature_entities(
                lines=lines,
                source_id=source.id,
            )
        ):
            entity_candidates.append(
                evidence
            )

        for index, line in enumerate(
            lines
        ):
            if not TRUE_UNIT_RE.search(
                line
            ):
                continue

            if self._is_court_registry_unit(
                lines=lines,
                index=index,
            ):
                continue

            unit_candidates.append(
                self._clean_unit(
                    line
                )
            )

    # ========================================================
    # SIGNATURE ENTITY
    # ========================================================

    def _extract_signature_entities(
        self,
        *,
        lines,
        source_id,
    ):
        if not lines:
            return []

        result = []

        # Use a larger signature zone because enterprise
        # disclaimers can be long, but body prose still cannot
        # become entity evidence unless it matches strong
        # organization grammar.
        tail = lines[-45:]

        for index, line in enumerate(
            tail
        ):
            entity = self._extract_entity_from_signature_line(
                line
            )

            if not entity:
                continue

            if SIGNATURE_EVIDENCE_BLOCK_RE.search(
                entity
            ):
                continue

            if self._entity_is_narrative(
                entity
            ):
                continue

            if PUBLIC_ENTITY_NAME_RE.search(
                entity
            ):
                result.append(
                    SemanticEntityEvidence(
                        name=entity,
                        entity_type="institution",
                        method="signature_public_entity",
                        source_id=source_id,
                        confidence=0.99,
                    )
                )
                continue

            if LEGAL_ENTITY_RE.search(
                entity
            ):
                result.append(
                    SemanticEntityEvidence(
                        name=entity,
                        entity_type="company",
                        method="signature_legal_entity",
                        source_id=source_id,
                        confidence=1.00,
                    )
                )
                continue

            neighborhood = " ".join(
                tail[
                    max(0, index - 5):
                    min(
                        len(tail),
                        index + 7,
                    )
                ]
            )

            structured_context = bool(
                NIP_RE.search(
                    neighborhood
                )
                or "regon" in neighborhood.casefold()
                or "www." in neighborhood.casefold()
                or "http" in neighborhood.casefold()
                or ROLE_RE.search(
                    neighborhood
                )
            )

            if (
                structured_context
                and self._looks_entity_name(
                    entity
                )
            ):
                result.append(
                    SemanticEntityEvidence(
                        name=entity,
                        entity_type=self._classify_entity(
                            entity
                        ),
                        method="signature_structured_entity",
                        source_id=source_id,
                        confidence=0.96,
                    )
                )

        return result

    @classmethod
    def _extract_entity_from_signature_line(
        cls,
        line,
    ):
        value = cls._clean_entity(
            line
        )

        if not value:
            return ""

        if (
            value.casefold()
            in BODY_NOISE_ENTITY_EXACT
        ):
            return ""

        if SIGNATURE_EVIDENCE_BLOCK_RE.search(
            value
        ):
            return ""

        if cls._entity_is_narrative(
            value
        ):
            # Narrative/privacy lines may still contain an exact
            # legal organization. Recover only that organization.
            return cls._recover_embedded_legal_entity(
                value
            )

        legal_match = LEGAL_ENTITY_RE.search(
            value
        )

        if legal_match:
            # Stop exactly at the legal form, then remove a prose
            # prefix such as:
            # "administratorem korespondencją jest Winda-Warszawa ..."
            prefix = cls._clean_entity(
                value[
                    :legal_match.end()
                ]
            )

            prefix = cls._trim_legal_entity_prefix(
                prefix
            )

            if (
                prefix
                and not cls._entity_is_narrative(
                    prefix
                )
            ):
                return prefix

        return value

    @classmethod
    def _trim_legal_entity_prefix(
        cls,
        value,
    ):
        value = cls._clean_entity(
            value
        )

        if not value:
            return ""

        # Prefer the final clause after a narrative copula only
        # when that clause itself still contains a legal form.
        parts = re.split(
            r"\b(?:jest|to)\b\s*",
            value,
            flags=re.IGNORECASE,
        )

        if len(parts) > 1:
            candidate = cls._clean_entity(
                parts[-1]
            )

            if (
                candidate
                and LEGAL_ENTITY_RE.search(
                    candidate
                )
            ):
                return candidate

        return value

    @classmethod
    def _recover_embedded_legal_entity(
        cls,
        value,
    ):
        # Strong quoted form:
        # "A.Weber" Spółka z o.o.
        quoted = re.search(
            r'["„”]([^"„”]{1,80})["„”]\s*'
            r'('
            r'Spółka\s+z\s+o\.?\s*o\.?'
            r'|Spolka\s+z\s+o\.?\s*o\.?'
            r'|Sp\.?\s*z\.?\s*o\.?\s*o\.?'
            r'|S\.?A\.?'
            r')',
            value,
            re.IGNORECASE,
        )

        if quoted:
            return cls._clean_entity(
                f"{quoted.group(1)} "
                f"{quoted.group(2)}"
            )

        # Unquoted narrative form:
        # "... jest Winda-Warszawa sp. z o.o."
        legal_match = LEGAL_ENTITY_RE.search(
            value
        )

        if not legal_match:
            return ""

        prefix = cls._clean_entity(
            value[
                :legal_match.end()
            ]
        )

        trimmed = cls._trim_legal_entity_prefix(
            prefix
        )

        if (
            trimmed != prefix
            and LEGAL_ENTITY_RE.search(
                trimmed
            )
        ):
            return trimmed

        return ""

    # ========================================================
    # SIGNATURE CONTACT
    # ========================================================

    def _extract_signature_contact(
        self,
        *,
        lines,
        candidate_email,
        source_id,
    ) -> SemanticContact | None:
        if not lines:
            return None

        email_index = None

        for index, line in enumerate(
            lines
        ):
            if (
                candidate_email
                and candidate_email
                in line.casefold()
            ):
                email_index = index
                break

        search_end = (
            email_index
            if email_index is not None
            else len(lines)
        )

        start = max(
            0,
            search_end - 18,
        )

        window = lines[
            start:search_end + 1
        ]

        for line in window:
            parsed = self._split_title_person(
                line
            )

            if parsed is None:
                continue

            person_name, title = parsed

            if self._looks_person_name(
                person_name
            ):
                return SemanticContact(
                    name=person_name,
                    role=None,
                    email=candidate_email or None,
                    phone=self._find_phone(
                        window
                    ),
                    source_ids=(source_id,),
                    confidence=0.995,
                )

        for role_index, line in enumerate(
            window
        ):
            if not ROLE_RE.search(
                line
            ):
                continue

            # Inline:
            # Paweł MOŁDRZIK | Specjalista ...
            if "|" in line:
                left, right = [
                    self._clean(part)
                    for part in line.split(
                        "|",
                        1,
                    )
                ]

                if (
                    self._looks_person_name(
                        left
                    )
                    and ROLE_RE.search(
                        right
                    )
                ):
                    return SemanticContact(
                        name=left,
                        role=right,
                        email=candidate_email or None,
                        phone=self._find_phone(
                            window[
                                role_index:
                                role_index + 8
                            ]
                        ),
                        source_ids=(source_id,),
                        confidence=0.995,
                    )

            for offset in range(
                role_index - 1,
                max(-1, role_index - 4),
                -1,
            ):
                candidate_name = (
                    self._sanitize_contact_name(
                        window[offset]
                    )
                )

                if self._looks_person_name(
                    candidate_name
                ):
                    return SemanticContact(
                        name=candidate_name,
                        role=line,
                        email=candidate_email or None,
                        phone=self._find_phone(
                            window[
                                role_index:
                                role_index + 6
                            ]
                        ),
                        source_ids=(source_id,),
                        confidence=0.99,
                    )

        for index, line in enumerate(
            window
        ):
            normalized = (
                self._normalize_identity(
                    line
                )
            )

            if normalized not in {
                "pozdrawiam",
                "z powazaniem",
                "z wyrazami szacunku",
                "serdecznie pozdrawiam",
            }:
                continue

            for next_index in range(
                index + 1,
                min(
                    len(window),
                    index + 5,
                ),
            ):
                candidate_name = (
                    self._sanitize_contact_name(
                        window[next_index]
                    )
                )

                if self._looks_person_name(
                    candidate_name
                ):
                    return SemanticContact(
                        name=candidate_name,
                        email=candidate_email or None,
                        source_ids=(source_id,),
                        confidence=0.95,
                    )

        return None

    # ========================================================
    # DISPLAY SPLIT
    # ========================================================

    def _split_person_entity_display(
        self,
        value,
    ):
        value = self._clean(
            value
        )

        if not value:
            return None

        for separator in (
            " | ",
            " - ",
        ):
            if separator not in value:
                continue

            left, right = [
                self._clean(part)
                for part in value.split(
                    separator,
                    1,
                )
            ]

            if (
                self._looks_person_name(
                    left
                )
                and self._looks_entity_name(
                    right
                )
            ):
                return (
                    left,
                    right,
                )

        tokens = value.split()

        if len(tokens) < 3:
            return None

        for split_index in (
            2,
            3,
        ):
            if len(tokens) <= split_index:
                continue

            person = self._sanitize_contact_name(
                " ".join(
                    tokens[:split_index]
                )
            )

            entity = self._clean_entity(
                " ".join(
                    tokens[split_index:]
                )
            )

            if (
                self._looks_person_name(
                    person
                )
                and self._looks_entity_name(
                    entity
                )
            ):
                return (
                    person,
                    entity,
                )

        return None

    # ========================================================
    # BASE ENTITY
    # ========================================================

    @classmethod
    def _sanitize_base_entity(
        cls,
        value,
    ):
        value = cls._clean_entity(
            value
        )

        if not value:
            return ""

        if (
            value.casefold()
            in BODY_NOISE_ENTITY_EXACT
        ):
            return ""

        if cls._entity_is_narrative(
            value
        ):
            return ""

        return value

    @classmethod
    def _entity_is_narrative(
        cls,
        value,
    ):
        value = cls._clean(
            value
        )

        if not value:
            return True

        lowered = value.casefold()

        if any(
            marker in lowered
            for marker in NARRATIVE_MARKERS
        ):
            return True

        if len(value) > 120:
            return True

        tokens = value.split()

        if (
            len(tokens) > 12
            and not LEGAL_ENTITY_RE.search(
                value
            )
            and not PUBLIC_ENTITY_RE.search(
                value
            )
        ):
            return True

        return False

    # ========================================================
    # CONTACT DEDUPE
    # ========================================================

    def _dedupe_contacts(
        self,
        values,
    ):
        grouped = {}

        for item in values:
            name = self._sanitize_contact_name(
                item.name
            )

            if not self._looks_person_name(
                name
            ):
                continue

            key = self._normalize_identity(
                name
            )

            if not key:
                continue

            cleaned = SemanticContact(
                name=name,
                role=self._clean(
                    item.role
                )
                or None,
                email=self._normalize_email(
                    item.email
                )
                or None,
                phone=self._clean_phone(
                    item.phone
                )
                or None,
                source_ids=item.source_ids,
                confidence=item.confidence,
            )

            matched_key = key

            if cleaned.email:
                for existing_key, existing_contact in grouped.items():
                    if (
                        existing_contact.email == cleaned.email
                        and self._names_equivalent(
                            existing_contact.name,
                            cleaned.name,
                        )
                    ):
                        matched_key = existing_key
                        break

            existing = grouped.get(
                matched_key
            )

            if existing is None:
                grouped[matched_key] = cleaned
            else:
                grouped[matched_key] = (
                    self._merge_contacts(
                        existing,
                        cleaned,
                    )
                )

        return sorted(
            grouped.values(),
            key=lambda item: (
                -item.confidence,
                self._normalize_identity(
                    item.name
                ),
            ),
        )

    @classmethod
    def _names_equivalent(
        cls,
        left,
        right,
    ):
        left_norm = cls._normalize_identity(
            left
        )
        right_norm = cls._normalize_identity(
            right
        )

        if not left_norm or not right_norm:
            return False

        if left_norm == right_norm:
            return True

        left_tokens = left_norm.split()
        right_tokens = right_norm.split()

        # Reversed two-part names:
        # "Marcin Peek" == "Peek, Marcin".
        if (
            len(left_tokens) == 2
            and len(right_tokens) == 2
            and sorted(left_tokens) == sorted(right_tokens)
        ):
            return True

        # Initial + surname variants:
        # "M Mroczek" == "Marcin Mroczek".
        if (
            len(left_tokens) == 2
            and len(right_tokens) == 2
        ):
            for short, full in (
                (left_tokens, right_tokens),
                (right_tokens, left_tokens),
            ):
                if (
                    len(short[0]) == 1
                    and full[0].startswith(short[0])
                    and short[1] == full[1]
                ):
                    return True

                if (
                    len(short[1]) == 1
                    and full[1].startswith(short[1])
                    and short[0] == full[0]
                ):
                    return True

        return False

    def _merge_contacts(
        self,
        left,
        right,
    ):
        preferred = (
            left
            if left.confidence
            >= right.confidence
            else right
        )

        other = (
            right
            if preferred is left
            else left
        )

        return SemanticContact(
            name=self._prefer_display_name(
                preferred.name,
                other.name,
            ),
            role=(
                preferred.role
                or other.role
            ),
            email=(
                preferred.email
                or other.email
            ),
            phone=(
                preferred.phone
                or other.phone
            ),
            source_ids=tuple(
                sorted(
                    set(
                        left.source_ids
                        + right.source_ids
                    )
                )
            ),
            confidence=max(
                left.confidence,
                right.confidence,
            ),
        )

    @classmethod
    def _prefer_display_name(
        cls,
        left,
        right,
    ):
        def score(value):
            value = cls._clean(
                value
            )

            polish = sum(
                character
                in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
                for character in value
            )

            punctuation = sum(
                not character.isalnum()
                and not character.isspace()
                and character not in "-'"
                for character in value
            )

            return (
                polish * 10
                + len(value)
                - punctuation * 4
            )

        return max(
            (
                left,
                right,
            ),
            key=score,
        )

    # ========================================================
    # ENTITY RANKING
    # ========================================================

    def _best_entity(
        self,
        values,
    ):
        if not values:
            return None

        grouped = {}

        for evidence in values:
            name = self._clean_entity(
                evidence.name
            )

            if not name:
                continue

            if self._entity_is_narrative(
                name
            ):
                continue

            key = self._normalize_identity(
                name
            )

            if not key:
                continue

            current = grouped.get(
                key
            )

            if (
                current is None
                or evidence.confidence
                > current.confidence
            ):
                grouped[key] = evidence

        if not grouped:
            return None

        return sorted(
            grouped.values(),
            key=lambda item: (
                -item.confidence,
                -self._entity_specificity(
                    item.name
                ),
                self._normalize_identity(
                    item.name
                ),
            ),
        )[0]

    @classmethod
    def _entity_specificity(
        cls,
        value,
    ):
        score = 0
        lowered = value.casefold()

        if LEGAL_ENTITY_RE.search(
            value
        ):
            score += 50

        if PUBLIC_ENTITY_RE.search(
            value
        ):
            score += 50

        if COMPANY_MARKER_RE.search(
            value
        ):
            score += 10

        # Prefer actual public-body names over URLs or metadata
        # that merely contain words such as "powiat".
        if PUBLIC_ENTITY_NAME_RE.search(
            value
        ):
            score += 40

        if SIGNATURE_EVIDENCE_BLOCK_RE.search(
            value
        ):
            score -= 100

        score += min(
            len(value),
            80,
        )

        return score

    # ========================================================
    # CONTACT / ENTITY CROSS VALIDATION
    # ========================================================

    @classmethod
    def _contact_overlaps_entity(
        cls,
        contact_name,
        entity_name,
    ):
        if not contact_name or not entity_name:
            return False

        contact = cls._normalize_identity(
            contact_name
        )

        entity = cls._normalize_identity(
            entity_name
        )

        if not contact or not entity:
            return False

        if contact == entity:
            return True

        if (
            len(contact.split()) >= 2
            and contact in entity
        ):
            return True

        return False

    # ========================================================
    # UNIT FILTER
    # ========================================================

    def _is_court_registry_unit(
        self,
        *,
        lines,
        index,
    ):
        line = lines[index]

        if not COURT_UNIT_RE.search(
            line
        ):
            return False

        context = " ".join(
            lines[
                max(0, index - 6):
                min(
                    len(lines),
                    index + 4,
                )
            ]
        )

        return bool(
            COURT_CONTEXT_RE.search(
                context
            )
            or re.search(
                r"krajowego rejestru|krs",
                line,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def _looks_court_unit(
        value,
    ):
        return bool(
            value
            and COURT_UNIT_RE.search(
                value
            )
        )

    def _dedupe_units(
        self,
        values,
    ):
        result = []
        seen = set()

        for value in values:
            value = self._clean_unit(
                value
            )

            if not value:
                continue

            if self._looks_court_unit(
                value
            ):
                continue

            key = self._normalize_identity(
                value
            )

            if not key or key in seen:
                continue

            seen.add(key)
            result.append(value)

        return result

    # ========================================================
    # CLASSIFICATION
    # ========================================================

    @classmethod
    def _looks_entity_name(
        cls,
        value,
    ):
        value = cls._clean_entity(
            value
        )

        if not value:
            return False

        if cls._entity_is_narrative(
            value
        ):
            return False

        if EMAIL_RE.match(
            value
        ):
            return False

        if SIGNATURE_EVIDENCE_BLOCK_RE.search(
            value
        ):
            return False

        if (
            value.casefold()
            in BODY_NOISE_ENTITY_EXACT
        ):
            return False

        if PUBLIC_ENTITY_NAME_RE.search(
            value
        ):
            return True

        if LEGAL_ENTITY_RE.search(
            value
        ):
            return True

        if COMPANY_MARKER_RE.search(
            value
        ):
            return (
                len(
                    value.split()
                )
                <= 8
            )

        tokens = value.split()

        if (
            1 <= len(tokens) <= 4
            and len(value) >= 4
            and all(
                token.upper() == token
                and any(
                    char.isalpha()
                    for char in token
                )
                for token in tokens
            )
        ):
            return True

        return False

    @classmethod
    def _looks_person_name(
        cls,
        value,
    ):
        value = cls._sanitize_contact_name(
            value
        )

        if not value:
            return False

        if EMAIL_RE.match(
            value
        ):
            return False

        if SIGNATURE_EVIDENCE_BLOCK_RE.search(
            value
        ):
            return False

        if value.startswith("["):
            return False

        lowered_value = value.casefold()

        if lowered_value.startswith(
            (
                "temat:",
                "odpowiedź-do:",
                "odpowiedz-do:",
                "from:",
                "subject:",
            )
        ):
            return False

        if PERSON_ORG_HINT_RE.search(
            value
        ):
            return False

        if cls._looks_entity_name(
            value
        ):
            return False

        if ROLE_RE.search(
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

        blocked = {
            "dzień",
            "dzien",
            "dobry",
            "witam",
            "pozdrawiam",
            "powiat",
            "oddział",
            "oddzial",
            "wydział",
            "wydzial",
            "telefon",
            "kontakt",
            "proszę",
            "prosze",
            "serdecznie",
            "drogi",
            "panie",
            "uwaga",
            "attention",
            "rodo",
        }

        if any(
            token.casefold() in blocked
            for token in tokens
        ):
            return False

        return True

    @classmethod
    def _classify_entity(
        cls,
        value,
    ):
        if PUBLIC_ENTITY_RE.search(
            value
        ):
            return "institution"

        return "company"

    # ========================================================
    # GENERIC HELPERS
    # ========================================================

    @classmethod
    def _clean_entity(
        cls,
        value,
    ):
        value = cls._clean(
            value
        )

        if not value:
            return ""

        return value.strip(
            "*_ "
        )

    @classmethod
    def _sanitize_contact_name(
        cls,
        value,
    ):
        value = cls._clean(
            value
        )

        if not value:
            return ""

        value = value.strip(
            "*_|_,"
        )

        normalized = cls._normalize_identity(
            value
        )

        if normalized in {
            cls._normalize_identity(item)
            for item in BAD_CONTACT_EXACT
        }:
            return ""

        lowered = value.casefold()

        if any(
            fragment in lowered
            for fragment in BAD_CONTACT_FRAGMENTS
        ):
            return ""

        value = re.sub(
            r"\s+[|/-]\s*$",
            "",
            value,
        ).strip()

        return value

    @classmethod
    def _split_title_person(
        cls,
        value,
    ):
        value = cls._clean(
            value
        )

        match = TITLE_PERSON_RE.match(
            value
        )

        if not match:
            return None

        person = cls._sanitize_contact_name(
            match.group(1)
        )

        if not person:
            return None

        prefix_length = (
            len(value)
            - len(match.group(1))
        )

        title = value[
            :prefix_length
        ].strip()

        if not title:
            return None

        return (
            person,
            title,
        )

    @staticmethod
    def _header_identity(
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
            return (
                "",
                "",
            )

        values = field.get(
            "value"
        )

        if not isinstance(
            values,
            list,
        ):
            return (
                "",
                "",
            )

        for item in values:
            if not isinstance(
                item,
                dict,
            ):
                continue

            return (
                str(
                    item.get("address")
                    or ""
                )
                .strip()
                .casefold(),
                str(
                    item.get("name")
                    or ""
                )
                .strip(),
            )

        return (
            "",
            "",
        )

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
            value = payload.get(
                key
            )

            if value not in (
                None,
                "",
            ):
                return str(
                    value
                ).strip()

        return ""

    @staticmethod
    def _find_phone(
        lines,
    ):
        for line in lines:
            match = PHONE_RE.search(
                line
            )

            if match:
                return (
                    ClientEntitySemanticProjectionService
                    ._clean_phone(
                        match.group(0)
                    )
                )

        return None

    @staticmethod
    def _clean_phone(
        value,
    ):
        if not value:
            return ""

        digits = re.sub(
            r"\D",
            "",
            str(value),
        )

        if (
            len(digits) == 11
            and digits.startswith(
                "48"
            )
        ):
            digits = digits[2:]

        if len(digits) != 9:
            return ""

        if digits.startswith(
            "00"
        ):
            return ""

        return digits

    @staticmethod
    def _normalize_email(
        value,
    ):
        if not value:
            return ""

        value = (
            str(value)
            .strip()
            .casefold()
        )

        if not EMAIL_RE.match(
            value
        ):
            return ""

        return value

    @staticmethod
    def _clean_unit(
        value,
    ):
        return (
            ClientEntitySemanticProjectionService
            ._clean(
                value
            )
            .rstrip(
                " :;,."
            )
        )

    @staticmethod
    def _clean(
        value,
    ):
        if value is None:
            return ""

        return " ".join(
            str(value)
            .replace("\r", " ")
            .replace("\n", " ")
            .split()
        )

    @staticmethod
    def _normalize_identity(
        value,
    ):
        if not value:
            return ""

        text = unicodedata.normalize(
            "NFKD",
            str(value),
        )

        text = "".join(
            character
            for character in text
            if not unicodedata.combining(
                character
            )
        )

        text = (
            text
            .replace("Ł", "L")
            .replace("ł", "l")
            .casefold()
        )

        text = re.sub(
            r"[^a-z0-9]+",
            " ",
            text,
        )

        return " ".join(
            text.split()
        )
