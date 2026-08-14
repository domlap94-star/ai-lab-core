from __future__ import annotations

import re
from collections import Counter

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate


ORG_MARKERS = (
    "sp. z o.o",
    "sp z o.o",
    "sp. z o. o",
    "spółka",
    "spolka",
    "s.a.",
    " s.a",
    "s.c.",
    " s.c",
    "invest",
    "development",
    "developer",
    "bud",
    "projekt",
    "biuro",
    "centrum",
    "firma",
    "group",
    "grupa",
    "holding",
    "system",
    "construction",
    "technologies",
    "tech",
    "domy",
    "nieruchomo",
    "wspólnot",
    "wspolnot",
    "spółdziel",
    "spoldziel",
    "powiat",
    "starost",
    "urząd",
    "urzad",
    "gmina",
    "miasto",
    "szkoła",
    "szkola",
    "szpital",
    "fundacja",
    "stowarzyszenie",
    "parafia",
    "zakład",
    "zaklad",
)


PUBLIC_MARKERS = (
    "powiat",
    "starost",
    "urząd",
    "urzad",
    "gmina",
    "miasto",
    "miejski",
    "miejska",
    "miejski zarząd",
    "miejski zarzad",
)


def clean(value) -> str:
    if value is None:
        return ""

    return " ".join(
        str(value).strip().split()
    )


def looks_like_email(value: str) -> bool:
    return (
        "@" in value
        and "." in value
    )


def contains_org_marker(value: str) -> bool:
    lowered = value.casefold()

    return any(
        marker in lowered
        for marker in ORG_MARKERS
    )


def contains_public_marker(value: str) -> bool:
    lowered = value.casefold()

    return any(
        marker in lowered
        for marker in PUBLIC_MARKERS
    )


def person_shape(value: str) -> bool:
    """
    Conservative shape only.

    We are NOT asserting that the value is a real person.
    We only detect a probable human-name-shaped field.
    """
    if not value:
        return False

    if looks_like_email(value):
        return False

    if contains_org_marker(value):
        return False

    if any(
        character.isdigit()
        for character in value
    ):
        return False

    parts = value.split()

    if len(parts) < 2:
        return False

    if len(parts) > 4:
        return False

    return True


def classify_pair(
    first_field: str,
    second_field: str,
) -> str:
    first_person = person_shape(
        first_field
    )

    second_org = contains_org_marker(
        second_field
    )

    if first_person and second_org:
        return "person_plus_organization"

    if second_org:
        return "organization_in_second_field"

    if (
        first_person
        and second_field
    ):
        return "person_plus_unclassified_second"

    if first_person:
        return "person_only_first_field"

    if second_field:
        return "second_field_only_or_other"

    return "no_identity_pair"


def main() -> None:
    db = SessionLocal()

    try:
        sources = (
            db.query(CandidateSource)
            .filter(
                CandidateSource.deleted_at.is_(None),
                CandidateSource.source_type
                == "google_sheets_row",
            )
            .order_by(
                CandidateSource.id.asc()
            )
            .all()
        )

        counts = Counter()

        examples = {
            "person_plus_organization": [],
            "organization_in_second_field": [],
            "person_plus_unclassified_second": [],
        }

        candidate_type_counts = Counter()

        public_examples = []
        organization_examples = []

        for source in sources:
            payload = source.raw_payload or {}

            first_field = clean(
                payload.get("IMIĘ ")
                or payload.get("IMIĘ")
            )

            second_field = clean(
                payload.get("NAZWISKO")
            )

            category = classify_pair(
                first_field,
                second_field,
            )

            counts[category] += 1

            if (
                category in examples
                and len(examples[category]) < 100
            ):
                examples[category].append(
                    (
                        source.candidate_id,
                        source.id,
                        first_field,
                        second_field,
                        clean(
                            payload.get("E-MAIL")
                        ),
                        clean(
                            payload.get("TELEFON")
                        ),
                    )
                )

            candidate = (
                db.query(ClientCandidate)
                .filter(
                    ClientCandidate.id
                    == source.candidate_id
                )
                .first()
            )

            if candidate is not None:
                candidate_type_counts[
                    candidate.client_type
                ] += 1

            combined = " ".join(
                part
                for part in (
                    first_field,
                    second_field,
                )
                if part
            )

            if (
                contains_public_marker(combined)
                and len(public_examples) < 100
            ):
                public_examples.append(
                    (
                        source.candidate_id,
                        source.id,
                        first_field,
                        second_field,
                        candidate.client_type
                        if candidate
                        else None,
                        candidate.name
                        if candidate
                        else None,
                    )
                )

            if (
                contains_org_marker(second_field)
                and len(organization_examples) < 150
            ):
                organization_examples.append(
                    (
                        source.candidate_id,
                        source.id,
                        first_field,
                        second_field,
                        candidate.client_type
                        if candidate
                        else None,
                        candidate.name
                        if candidate
                        else None,
                    )
                )

        print()
        print("=" * 120)
        print("GOOGLE SHEETS IDENTITY FIELD SEMANTICS")
        print("=" * 120)

        print(
            "google_sheets_sources:",
            len(sources),
        )

        print()

        for key in (
            "person_plus_organization",
            "organization_in_second_field",
            "person_plus_unclassified_second",
            "person_only_first_field",
            "second_field_only_or_other",
            "no_identity_pair",
        ):
            print(
                key,
                ":",
                counts[key],
            )

        print()
        print("=" * 120)
        print("CURRENT CLIENT_TYPE FOR SHEET SOURCES")
        print("=" * 120)

        for client_type, count in sorted(
            candidate_type_counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        ):
            print(
                client_type,
                ":",
                count,
            )

        for category in (
            "person_plus_organization",
            "organization_in_second_field",
            "person_plus_unclassified_second",
        ):
            print()
            print("=" * 120)
            print(
                "EXAMPLES:",
                category,
            )
            print("=" * 120)

            for item in examples[category]:
                (
                    candidate_id,
                    source_id,
                    first_field,
                    second_field,
                    email,
                    phone,
                ) = item

                print(
                    candidate_id,
                    "| source",
                    source_id,
                    "| first:",
                    repr(first_field),
                    "| second:",
                    repr(second_field),
                    "| email:",
                    repr(email),
                    "| phone:",
                    repr(phone),
                )

        print()
        print("=" * 120)
        print("ORGANIZATION SECOND-FIELD EXAMPLES")
        print("=" * 120)

        for item in organization_examples:
            (
                candidate_id,
                source_id,
                first_field,
                second_field,
                client_type,
                candidate_name,
            ) = item

            print(
                candidate_id,
                "| source",
                source_id,
                "| person/contact:",
                repr(first_field),
                "| organization:",
                repr(second_field),
                "| current_type:",
                repr(client_type),
                "| current_name:",
                repr(candidate_name),
            )

        print()
        print("=" * 120)
        print("PUBLIC BODY EXAMPLES")
        print("=" * 120)

        for item in public_examples:
            (
                candidate_id,
                source_id,
                first_field,
                second_field,
                client_type,
                candidate_name,
            ) = item

            print(
                candidate_id,
                "| source",
                source_id,
                "| first:",
                repr(first_field),
                "| second:",
                repr(second_field),
                "| current_type:",
                repr(client_type),
                "| current_name:",
                repr(candidate_name),
            )

        print()
        print("=" * 120)
        print("DATABASE NOT MODIFIED")
        print("=" * 120)

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
