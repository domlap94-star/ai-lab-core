from __future__ import annotations

import re
import unicodedata
from collections import Counter

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.services.client_entity_semantic_projection_service import (
    ClientEntitySemanticProjectionService,
)


SUSPICIOUS_CONTACT_RE = re.compile(
    r"(?:"
    r"^z poważaniem[,]?$"
    r"|^z powazaniem[,]?$"
    r"|^pozdrawiam[,]?$"
    r"|^winda\s*-$"
    r"|^biuro$"
    r"|^firma$"
    r")",
    re.IGNORECASE,
)

SUSPICIOUS_ENTITY_TEXT_RE = re.compile(
    r"(?:"
    r"wszelkie inne informacje"
    r"|informacje zawarte"
    r"|niniejszej wiadomości"
    r"|niniejszej wiadomosci"
    r"|ochrona danych"
    r"|polityka prywatności"
    r"|polityka prywatnosci"
    r"|jeżeli państwo"
    r"|jezeli panstwo"
    r"|zamierzonego adresata"
    r"|intended recipient"
    r")",
    re.IGNORECASE,
)

SUSPICIOUS_ROLE_RE = re.compile(
    r"(?:"
    r"^[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+\s+"
    r"[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+$"
    r")"
)

COURT_UNIT_RE = re.compile(
    r"(?:wydział|wydzial).{0,20}gospodarczy",
    re.IGNORECASE,
)


CONTROL_IDS = {
    2535,
    2657,
    2764,
    3269,
    3305,
    3307,
    3323,
    3462,
    3489,
}


def clean(value):
    if value is None:
        return ""

    return " ".join(
        str(value).strip().split()
    )


def normalize(value):
    if not value:
        return ""

    text = unicodedata.normalize(
        "NFKD",
        str(value),
    )

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
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


def contact_signature(contact):
    return (
        normalize(contact.name),
        normalize(contact.email),
        re.sub(
            r"\D",
            "",
            contact.phone or "",
        ),
    )


def main():
    db = SessionLocal()

    try:
        service = (
            ClientEntitySemanticProjectionService(
                db
            )
        )

        candidates = (
            db.query(ClientCandidate)
            .filter(
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.status == "pending",
            )
            .order_by(
                ClientCandidate.id.asc()
            )
            .all()
        )

        status_counts = Counter()
        type_counts = Counter()

        duplicate_contacts = []
        suspicious_contacts = []
        suspicious_entities = []
        suspicious_phones = []
        suspicious_roles = []
        suspicious_units = []
        multi_contact_entities = []

        controls = {}

        for candidate in candidates:
            result = service.project(
                candidate
            )

            status_counts[
                result.status
            ] += 1

            type_counts[
                result.entity_type
            ] += 1

            if candidate.id in CONTROL_IDS:
                controls[
                    candidate.id
                ] = result

            # ================================================
            # MULTI-CONTACT
            # ================================================

            if len(result.contacts) > 1:
                multi_contact_entities.append(
                    (
                        candidate.id,
                        clean(candidate.name),
                        clean(result.entity_name),
                        [
                            (
                                contact.name,
                                contact.role,
                                contact.email,
                                contact.phone,
                            )
                            for contact
                            in result.contacts
                        ],
                    )
                )

            # ================================================
            # DUPLICATE CONTACTS AFTER DIACRITIC NORMALIZATION
            # ================================================

            normalized_names = {}

            for contact in result.contacts:
                key = normalize(
                    contact.name
                )

                if not key:
                    continue

                normalized_names.setdefault(
                    key,
                    [],
                ).append(
                    contact
                )

            for key, contacts in (
                normalized_names.items()
            ):
                if len(contacts) <= 1:
                    continue

                duplicate_contacts.append(
                    (
                        candidate.id,
                        clean(candidate.name),
                        clean(result.entity_name),
                        key,
                        [
                            (
                                item.name,
                                item.role,
                                item.email,
                                item.phone,
                                item.source_ids,
                            )
                            for item in contacts
                        ],
                    )
                )

            # ================================================
            # SUSPICIOUS CONTACT NAMES
            # ================================================

            for contact in result.contacts:
                contact_name = clean(
                    contact.name
                )

                if (
                    not contact_name
                    or SUSPICIOUS_CONTACT_RE.search(
                        contact_name
                    )
                ):
                    suspicious_contacts.append(
                        (
                            candidate.id,
                            clean(candidate.name),
                            clean(result.entity_name),
                            contact_name,
                            contact.role,
                            contact.email,
                            contact.phone,
                        )
                    )

            # ================================================
            # ENTITY TEXT CONTAMINATION
            # ================================================

            entity_name = clean(
                result.entity_name
            )

            if (
                entity_name
                and (
                    len(entity_name) > 100
                    or SUSPICIOUS_ENTITY_TEXT_RE.search(
                        entity_name
                    )
                )
            ):
                suspicious_entities.append(
                    (
                        candidate.id,
                        clean(candidate.name),
                        entity_name,
                        result.entity_type,
                    )
                )

            # ================================================
            # PHONE QUALITY
            # ================================================

            for contact in result.contacts:
                if not contact.phone:
                    continue

                digits = re.sub(
                    r"\D",
                    "",
                    contact.phone,
                )

                # Polish numbers projected as local contact
                # numbers should normally be 9 digits, but
                # reject obvious suspicious technical forms.
                suspicious = (
                    len(digits) != 9
                    or digits.startswith("00")
                    or len(set(digits)) <= 2
                )

                if suspicious:
                    suspicious_phones.append(
                        (
                            candidate.id,
                            clean(candidate.name),
                            contact.name,
                            contact.phone,
                            contact.source_ids,
                        )
                    )

            # ================================================
            # ROLE / PERSON INVERSION
            # ================================================

            for contact in result.contacts:
                role = clean(
                    contact.role
                )

                if not role:
                    continue

                if (
                    "mgr " in role.casefold()
                    and len(role.split()) >= 3
                ):
                    suspicious_roles.append(
                        (
                            candidate.id,
                            clean(candidate.name),
                            contact.name,
                            role,
                            contact.email,
                        )
                    )

            # ================================================
            # COURT UNIT LEAKAGE
            # ================================================

            for unit in (
                result.organizational_units
            ):
                if COURT_UNIT_RE.search(
                    unit
                ):
                    suspicious_units.append(
                        (
                            candidate.id,
                            clean(candidate.name),
                            clean(result.entity_name),
                            unit,
                        )
                    )

        print()
        print("=" * 140)
        print(
            "CLIENT ENTITY PROJECTION 1.4 "
            "FULL QUALITY AUDIT"
        )
        print("=" * 140)

        print(
            "candidates:",
            len(candidates),
        )

        print()
        print("STATUS:")

        for key in sorted(
            status_counts
        ):
            print(
                key,
                ":",
                status_counts[key],
            )

        print()
        print("ENTITY TYPES:")

        for key in (
            "person",
            "company",
            "institution",
            "other",
        ):
            print(
                key,
                ":",
                type_counts[key],
            )

        sections = (
            (
                "DUPLICATE CONTACTS",
                duplicate_contacts,
            ),
            (
                "SUSPICIOUS CONTACT NAMES",
                suspicious_contacts,
            ),
            (
                "SUSPICIOUS ENTITY NAMES",
                suspicious_entities,
            ),
            (
                "SUSPICIOUS PHONE VALUES",
                suspicious_phones,
            ),
            (
                "SUSPICIOUS CONTACT ROLES",
                suspicious_roles,
            ),
            (
                "COURT/KRS UNIT LEAKAGE",
                suspicious_units,
            ),
            (
                "MULTI-CONTACT ENTITIES",
                multi_contact_entities,
            ),
        )

        for title, rows in sections:
            print()
            print("=" * 140)
            print(title)
            print("=" * 140)
            print(
                "count:",
                len(rows),
            )

            for row in rows[:150]:
                print(row)

            if len(rows) > 150:
                print(
                    "...",
                    len(rows) - 150,
                    "MORE",
                )

        print()
        print("=" * 140)
        print("CONTROL RESULTS")
        print("=" * 140)

        for candidate_id in sorted(
            CONTROL_IDS
        ):
            result = controls.get(
                candidate_id
            )

            print()
            print("-" * 140)

            if result is None:
                print(
                    candidate_id,
                    "| NOT FOUND"
                )
                continue

            print(
                "candidate_id:",
                candidate_id,
            )

            print(
                "entity:",
                repr(
                    result.entity_name
                ),
            )

            print(
                "type:",
                result.entity_type,
            )

            print(
                "tax:",
                repr(
                    result.tax_id
                ),
            )

            print(
                "units:",
                result.organizational_units,
            )

            print(
                "contacts:",
            )

            for contact in result.contacts:
                print(
                    "  ",
                    repr(contact.name),
                    "| role:",
                    repr(contact.role),
                    "| email:",
                    repr(contact.email),
                    "| phone:",
                    repr(contact.phone),
                    "| sources:",
                    contact.source_ids,
                )

        print()
        print("=" * 140)
        print("SUMMARY COUNTS")
        print("=" * 140)

        print(
            "duplicate_contact_candidates:",
            len(duplicate_contacts),
        )

        print(
            "suspicious_contact_candidates:",
            len(suspicious_contacts),
        )

        print(
            "suspicious_entity_candidates:",
            len(suspicious_entities),
        )

        print(
            "suspicious_phone_candidates:",
            len(suspicious_phones),
        )

        print(
            "suspicious_role_candidates:",
            len(suspicious_roles),
        )

        print(
            "court_unit_candidates:",
            len(suspicious_units),
        )

        print(
            "multi_contact_candidates:",
            len(multi_contact_entities),
        )

        print()
        print("=" * 140)
        print("SAFETY")
        print("=" * 140)

        print(
            "DATABASE MODIFICATIONS: 0"
        )

        print(
            "CLIENT CANDIDATE WRITES: 0"
        )

        print(
            "AUTO PROMOTIONS: 0"
        )

        print()
        print(
            "CLIENT ENTITY PROJECTION "
            "1.4 QUALITY AUDIT: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
