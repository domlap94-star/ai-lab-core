from __future__ import annotations

import unicodedata
from collections import Counter

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.services.client_entity_projection_service import (
    ClientEntityProjectionService,
)


CONTROL_IDS = {
    8,
    12,
    27,
    2067,
    2236,
    2285,
    2331,
    2688,
    2764,
    2998,
    3154,
    3269,
    3307,
    3474,
    3489,
    3507,
    3514,
    3521,
}


OWN_ENTITY_MARKERS = (
    "next stabil",
    "podnoszenie posadzek",
)

OWN_CONTACT_MARKERS = (
    "wojciech lapinski",
    "dominik lapinski",
    "podnoszenie posadzek",
)

OWN_TAX_IDS = {
    "8211139503",
    "8212697553",
}


def normalize(
    value: str | None,
) -> str:
    if not value:
        return ""

    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        character
        for character in normalized
        if not unicodedata.combining(
            character
        )
    )

    return (
        value.casefold()
        .replace("ł", "l")
    )


def print_projection(
    result,
) -> None:
    print()
    print("-" * 120)

    print(
        "candidate_id:",
        result.candidate_id,
    )

    print(
        "current_name:",
        repr(result.current_name),
    )

    print(
        "current_client_type:",
        repr(
            result.current_client_type
        ),
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
        "legal_name:",
        repr(result.legal_name),
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
        "contact_phone:",
        repr(result.contact_phone),
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
        "confidence:",
        result.confidence,
    )

    print(
        "status:",
        result.status,
    )

    print(
        "reason:",
        result.reason,
    )

    print(
        "evidence:"
    )

    for evidence in result.evidence:
        print(
            "  ",
            evidence.method,
            "|",
            repr(evidence.value),
            "| source",
            evidence.source_id,
            "|",
            evidence.source_type,
        )


def main() -> None:
    db = SessionLocal()

    try:
        service = (
            ClientEntityProjectionService(
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

        results = []
        type_counts = Counter()
        status_counts = Counter()

        contamination = []

        for candidate in candidates:
            projection = service.project(
                candidate
            )

            results.append(
                projection
            )

            type_counts[
                projection.entity_type
            ] += 1

            status_counts[
                projection.status
            ] += 1

            entity = normalize(
                projection.entity_name
            )

            contact = normalize(
                projection.contact_name
            )

            tax_id = (
                projection.tax_id
                or ""
            )

            problems = []

            if any(
                marker in entity
                for marker in OWN_ENTITY_MARKERS
            ):
                problems.append(
                    "own_entity"
                )

            if any(
                marker in contact
                for marker in OWN_CONTACT_MARKERS
            ):
                problems.append(
                    "own_contact"
                )

            if tax_id in OWN_TAX_IDS:
                problems.append(
                    "own_tax_id"
                )

            if problems:
                contamination.append(
                    (
                        candidate.id,
                        candidate.name,
                        projection,
                        problems,
                    )
                )

        print()
        print("=" * 120)
        print(
            "CLIENT ENTITY PROJECTION 1.1 SUMMARY"
        )
        print("=" * 120)

        print(
            "candidates:",
            len(results),
        )

        print()
        print("ENTITY TYPES:")

        for entity_type in (
            "person",
            "company",
            "institution",
            "other",
        ):
            print(
                f"{entity_type}:",
                type_counts[entity_type],
            )

        print()
        print("STATUS:")

        for status in (
            "review",
            "insufficient",
        ):
            print(
                f"{status}:",
                status_counts[status],
            )

        print()
        print("=" * 120)
        print(
            "FIRST-PARTY CONTAMINATION CHECK"
        )
        print("=" * 120)

        print(
            "contaminated_candidates:",
            len(contamination),
        )

        for (
            candidate_id,
            current_name,
            projection,
            problems,
        ) in contamination[:100]:
            print(
                candidate_id,
                "|",
                repr(current_name),
                "| entity:",
                repr(projection.entity_name),
                "| contact:",
                repr(projection.contact_name),
                "| tax:",
                repr(projection.tax_id),
                "| problems:",
                problems,
            )

        print()
        print("=" * 120)
        print("CONTROL PROJECTIONS")
        print("=" * 120)

        by_id = {
            item.candidate_id: item
            for item in results
        }

        for candidate_id in sorted(
            CONTROL_IDS
        ):
            result = by_id.get(
                candidate_id
            )

            if result is None:
                print()
                print(
                    candidate_id,
                    "| NOT FOUND"
                )
                continue

            print_projection(
                result
            )

        print()
        print("=" * 120)
        print("ORGANIZATIONAL UNITS - ALL")
        print("=" * 120)

        units = [
            result
            for result in results
            if result.organizational_unit
        ]

        for result in units:
            print(
                result.candidate_id,
                "| entity:",
                repr(result.entity_name),
                "| contact:",
                repr(result.contact_name),
                "| unit:",
                repr(
                    result.organizational_unit
                ),
            )

        print()
        print(
            "organizational_unit_count:",
            len(units),
        )

        print()
        print("=" * 120)
        print("SAFETY")
        print("=" * 120)

        print(
            "DATABASE MODIFICATIONS: 0"
        )
        print(
            "AUTO PROMOTIONS: 0"
        )
        print(
            "AUTO CLIENT TYPE WRITES: 0"
        )

        if contamination:
            raise RuntimeError(
                "First-party identity contamination "
                "still exists."
            )

        print()
        print(
            "FIRST-PARTY CONTAMINATION: 0"
        )

        print()
        print(
            "CLIENT ENTITY PROJECTION "
            "1.1 DRY RUN: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
