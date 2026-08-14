from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.services.client_entity_projection_policy_service import (
    ClientEntityProjectionPolicyService,
)


CONTROL_IDS = {
    2067,
    2236,
    2285,
    2331,
    2764,
    2772,
    2998,
    3154,
    3269,
    3307,
    3462,
    3474,
    3489,
}


ORG_WORDS_RE = re.compile(
    r"(?:"
    r"\bsp\.?\s*z\.?\s*o\.?\s*o\.?\b"
    r"|\bs\.?\s*a\.?\b"
    r"|\bs\.?\s*c\.?\b"
    r"|\binvest\b"
    r"|\bconstruction\b"
    r"|\bdevelopment\b"
    r"|\bbiuro\b"
    r"|\bbud\b"
    r"|\bbuild\b"
    r"|\bgroup\b"
    r"|\burząd\b"
    r"|\burzad\b"
    r"|\bstarostwo\b"
    r"|\bpowiat\b"
    r"|\bgmina\b"
    r")",
    re.IGNORECASE,
)


SUSPICIOUS_UNIT_RE = re.compile(
    r"(?:"
    r"\bsąd\b"
    r"|\bsad\b"
    r"|\bkrs\b"
    r"|\brejestr\b"
    r"|\bkapitał\b"
    r"|\bkapital\b"
    r"|\bgospodarczy\b"
    r"|\bwydział gospodarczy\b"
    r"|\bwydzial gospodarczy\b"
    r")",
    re.IGNORECASE,
)


def clean(value):
    if value is None:
        return ""

    return " ".join(
        str(value).strip().split()
    )


def normalize(value):
    if not value:
        return ""

    value = unicodedata.normalize(
        "NFKD",
        str(value),
    )

    value = "".join(
        character
        for character in value
        if not unicodedata.combining(character)
    )

    value = (
        value
        .replace("Ł", "L")
        .replace("ł", "l")
        .casefold()
    )

    return " ".join(
        value.split()
    )


def header_identity(payload, field_name):
    field = payload.get(field_name)

    if not isinstance(field, dict):
        return []

    values = field.get("value")

    if not isinstance(values, list):
        return []

    result = []

    for item in values:
        if not isinstance(item, dict):
            continue

        address = clean(
            item.get("address")
        ).casefold()

        name = clean(
            item.get("name")
        )

        if address or name:
            result.append(
                (
                    address,
                    name,
                )
            )

    return result


def sheet_identity(payload):
    first_name = ""

    for key in (
        "IMIĘ ",
        "IMIĘ",
    ):
        value = clean(
            payload.get(key)
        )

        if value:
            first_name = value
            break

    last_name = clean(
        payload.get("NAZWISKO")
    )

    email = clean(
        payload.get("E-MAIL")
    ).casefold()

    return (
        first_name,
        last_name,
        email,
    )


def looks_personish_display(value):
    value = clean(value)

    if not value:
        return False

    if ORG_WORDS_RE.search(value):
        return False

    tokens = value.split()

    if not (
        2 <= len(tokens) <= 4
    ):
        return False

    if any(
        character.isdigit()
        for character in value
    ):
        return False

    return True


def print_rows(
    title,
    rows,
    *,
    limit=100,
):
    print()
    print("=" * 140)
    print(title)
    print("=" * 140)
    print("count:", len(rows))

    for row in rows[:limit]:
        print(row)

    if len(rows) > limit:
        print(
            f"... {len(rows) - limit} MORE ..."
        )


def main():
    db = SessionLocal()

    try:
        service = (
            ClientEntityProjectionPolicyService(
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

        missing_contact = []
        suspicious_person_org = []
        suspicious_units = []
        source_identity_conflicts = []

        type_counts = Counter()
        status_counts = Counter()

        control_results = {}

        for candidate in candidates:
            result = service.project(
                candidate
            )

            type_counts[
                result.entity_type
            ] += 1

            status_counts[
                result.status
            ] += 1

            if candidate.id in CONTROL_IDS:
                control_results[
                    candidate.id
                ] = result

            sources = (
                db.query(CandidateSource)
                .filter(
                    CandidateSource.candidate_id
                    == candidate.id,
                    CandidateSource.deleted_at.is_(None),
                )
                .order_by(
                    CandidateSource.id.asc()
                )
                .all()
            )

            gmail_displays = set()
            sheet_pairs = set()

            candidate_email = (
                clean(
                    candidate.primary_email
                )
                .casefold()
            )

            for source in sources:
                payload = (
                    source.raw_payload
                    or {}
                )

                if (
                    source.source_type
                    == "gmail_message"
                ):
                    for (
                        address,
                        display,
                    ) in header_identity(
                        payload,
                        "from",
                    ):
                        if (
                            candidate_email
                            and address
                            == candidate_email
                            and display
                        ):
                            gmail_displays.add(
                                display
                            )

                elif (
                    source.source_type
                    == "google_sheets_row"
                ):
                    (
                        first_name,
                        second_field,
                        sheet_email,
                    ) = sheet_identity(
                        payload
                    )

                    if (
                        first_name
                        or second_field
                    ):
                        sheet_pairs.add(
                            (
                                first_name,
                                second_field,
                                sheet_email,
                            )
                        )

            # =================================================
            # 1. ORGANIZATION WITH MISSING CONTACT
            # =================================================

            if (
                result.status == "review"
                and result.entity_type
                in (
                    "company",
                    "institution",
                )
                and not result.contact_name
            ):
                personish_displays = sorted(
                    display
                    for display
                    in gmail_displays
                    if looks_personish_display(
                        display
                    )
                )

                if personish_displays:
                    missing_contact.append(
                        (
                            candidate.id,
                            clean(candidate.name),
                            result.entity_name,
                            result.contact_email,
                            personish_displays,
                            sorted(sheet_pairs),
                        )
                    )

            # =================================================
            # 2. PERSON PROJECTION CONTAINING ORG SIGNAL
            # =================================================

            if (
                result.status == "review"
                and result.entity_type == "person"
            ):
                selected = clean(
                    result.entity_name
                )

                current = clean(
                    candidate.name
                )

                if (
                    ORG_WORDS_RE.search(
                        selected
                    )
                    or ORG_WORDS_RE.search(
                        current
                    )
                ):
                    suspicious_person_org.append(
                        (
                            candidate.id,
                            current,
                            selected,
                            result.contact_name,
                            result.contact_email,
                            sorted(gmail_displays),
                            sorted(sheet_pairs),
                        )
                    )

            # =================================================
            # 3. SUSPICIOUS ORGANIZATIONAL UNIT
            # =================================================

            unit = clean(
                result.organizational_unit
            )

            if unit:
                normalized_unit = (
                    normalize(unit)
                )

                if (
                    SUSPICIOUS_UNIT_RE.search(
                        unit
                    )
                    or normalized_unit.startswith(
                        "w warszawie"
                    )
                    or normalized_unit.startswith(
                        "w krakowie"
                    )
                    or normalized_unit.startswith(
                        "w poznaniu"
                    )
                ):
                    suspicious_units.append(
                        (
                            candidate.id,
                            clean(candidate.name),
                            result.entity_name,
                            unit,
                            [
                                (
                                    evidence.method,
                                    evidence.value,
                                    evidence.source_id,
                                )
                                for evidence
                                in result.evidence
                            ],
                        )
                    )

            # =================================================
            # 4. SHEETS / GMAIL IDENTITY DISAGREEMENT
            # =================================================

            if (
                sheet_pairs
                and gmail_displays
            ):
                sheet_tokens = set()

                for (
                    first_name,
                    second_field,
                    _,
                ) in sheet_pairs:
                    for value in (
                        first_name,
                        second_field,
                    ):
                        normalized = normalize(
                            value
                        )

                        if normalized:
                            sheet_tokens.add(
                                normalized
                            )

                gmail_tokens = {
                    normalize(display)
                    for display
                    in gmail_displays
                    if normalize(display)
                }

                if (
                    sheet_tokens
                    and gmail_tokens
                    and not any(
                        (
                            sheet_value
                            in gmail_value
                            or gmail_value
                            in sheet_value
                        )
                        for sheet_value
                        in sheet_tokens
                        for gmail_value
                        in gmail_tokens
                    )
                ):
                    source_identity_conflicts.append(
                        (
                            candidate.id,
                            clean(candidate.name),
                            result.entity_name,
                            result.contact_name,
                            sorted(sheet_pairs),
                            sorted(gmail_displays),
                        )
                    )

        print()
        print("=" * 140)
        print(
            "CLIENT ENTITY SEMANTIC QUALITY AUDIT 1.0"
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

        print_rows(
            "ORGANIZATIONS WITH MISSING CONTACT "
            "DESPITE PERSON-LIKE GMAIL DISPLAY",
            missing_contact,
        )

        print_rows(
            "PERSON PROJECTIONS WITH ORGANIZATION SIGNAL",
            suspicious_person_org,
        )

        print_rows(
            "SUSPICIOUS ORGANIZATIONAL UNITS",
            suspicious_units,
        )

        print_rows(
            "POTENTIAL GOOGLE SHEETS / GMAIL IDENTITY CONFLICTS",
            source_identity_conflicts,
        )

        print()
        print("=" * 140)
        print("CONTROL PROJECTIONS")
        print("=" * 140)

        for candidate_id in sorted(
            CONTROL_IDS
        ):
            result = control_results.get(
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
                result.candidate_id,
            )

            print(
                "current_name:",
                repr(result.current_name),
            )

            print(
                "entity_name:",
                repr(result.entity_name),
            )

            print(
                "entity_type:",
                repr(result.entity_type),
            )

            print(
                "contact_name:",
                repr(result.contact_name),
            )

            print(
                "contact_email:",
                repr(result.contact_email),
            )

            print(
                "organizational_unit:",
                repr(
                    result.organizational_unit
                ),
            )

            print(
                "tax_id:",
                repr(result.tax_id),
            )

            print(
                "status:",
                result.status,
            )

            print(
                "evidence:",
            )

            for evidence in result.evidence:
                print(
                    "  ",
                    evidence.method,
                    "|",
                    repr(evidence.value),
                    "| source",
                    evidence.source_id,
                )

        print()
        print("=" * 140)
        print("SUMMARY COUNTS")
        print("=" * 140)

        print(
            "missing_contact_candidates:",
            len(missing_contact),
        )

        print(
            "person_with_org_signal_candidates:",
            len(suspicious_person_org),
        )

        print(
            "suspicious_org_unit_candidates:",
            len(suspicious_units),
        )

        print(
            "sheet_gmail_conflict_candidates:",
            len(source_identity_conflicts),
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
            "CLIENT ENTITY SEMANTIC QUALITY AUDIT 1.0: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
