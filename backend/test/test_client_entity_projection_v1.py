from __future__ import annotations

from collections import Counter

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.services.client_entity_projection_service import (
    ClientEntityProjectionService,
)


CONTROL_IDS = {
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

        type_counts = Counter()
        status_counts = Counter()

        projections = []

        for candidate in candidates:
            projection = service.project(
                candidate
            )

            projections.append(
                projection
            )

            type_counts[
                projection.entity_type
            ] += 1

            status_counts[
                projection.status
            ] += 1

        print()
        print("=" * 120)
        print("CLIENT ENTITY PROJECTION 1.0 SUMMARY")
        print("=" * 120)

        print(
            "candidates:",
            len(projections),
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
        print("PROJECTION STATUS:")

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
        print("CONTROL PROJECTIONS")
        print("=" * 120)

        by_id = {
            item.candidate_id: item
            for item in projections
        }

        for candidate_id in sorted(
            CONTROL_IDS
        ):
            result = by_id.get(
                candidate_id
            )

            print()
            print("-" * 120)

            if result is None:
                print(
                    candidate_id,
                    "| NOT FOUND / NOT PENDING",
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

            print("evidence:")

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

        print()
        print("=" * 120)
        print("COMPANY / INSTITUTION PROJECTIONS - FIRST 150")
        print("=" * 120)

        organizational = [
            item
            for item in projections
            if item.entity_type
            in (
                "company",
                "institution",
            )
        ]

        for item in organizational[:150]:
            print(
                item.candidate_id,
                "|",
                repr(item.current_name),
                "=> entity:",
                repr(item.entity_name),
                "| type:",
                item.entity_type,
                "| contact:",
                repr(item.contact_name),
                "| unit:",
                repr(
                    item.organizational_unit
                ),
                "| confidence:",
                item.confidence,
            )

        print()
        print(
            "organizational_projection_count:",
            len(organizational),
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

        print()
        print(
            "CLIENT ENTITY PROJECTION "
            "1.0 DRY RUN: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
