from __future__ import annotations

import unicodedata
from collections import Counter

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.services.client_entity_projection_service import (
    ClientEntityProjectionService,
)


CONTROL_IDS = {
    27,
    133,
    221,
    603,
    720,
    1111,
    2067,
    2236,
    2285,
    2331,
    2595,
    2688,
    2764,
    2998,
    3095,
    3154,
    3269,
    3307,
    3344,
    3462,
    3474,
    3489,
}


OWN_TAX_IDS = {
    "8211139503",
    "8212697553",
}

OWN_CONTACT_MARKERS = (
    "dominik lapinski",
    "wojciech lapinski",
    "podnoszenie posadzek",
)

OWN_ENTITY_MARKERS = (
    "next stabil",
    "podnoszenie posadzek",
)


def normalize(
    value: str | None,
) -> str:
    if not value:
        return ""

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        character
        for character in value
        if not unicodedata.combining(
            character
        )
    )

    return (
        value.casefold()
        .replace("ł", "l")
    )


def main():
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

        statuses = Counter()
        types = Counter()

        own_tax = []
        own_contact = []
        own_entity = []

        relay_containers = []

        for candidate in candidates:
            result = service.project(
                candidate
            )

            results.append(
                result
            )

            statuses[
                result.status
            ] += 1

            types[
                result.entity_type
            ] += 1

            if (
                result.tax_id
                in OWN_TAX_IDS
            ):
                own_tax.append(
                    result
                )

            contact = normalize(
                result.contact_name
            )

            if any(
                marker in contact
                for marker
                in OWN_CONTACT_MARKERS
            ):
                own_contact.append(
                    result
                )

            entity = normalize(
                result.entity_name
            )

            if any(
                marker in entity
                for marker
                in OWN_ENTITY_MARKERS
            ):
                own_entity.append(
                    result
                )

            if (
                result.status
                == "relay_container"
            ):
                relay_containers.append(
                    result
                )

        print()
        print("=" * 120)
        print(
            "CLIENT ENTITY PROJECTION 1.2 SUMMARY"
        )
        print("=" * 120)

        print(
            "candidates:",
            len(results),
        )

        print()
        print("STATUS:")

        for key in sorted(
            statuses
        ):
            print(
                key,
                ":",
                statuses[key],
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
                types[key],
            )

        print()
        print("=" * 120)
        print("FIRST-PARTY TAX CONTAMINATION")
        print("=" * 120)

        print(
            "own_tax_candidates:",
            len(own_tax),
        )

        for result in own_tax:
            print(
                result.candidate_id,
                "|",
                repr(result.current_name),
                "| tax:",
                repr(result.tax_id),
                "| evidence:",
                [
                    (
                        item.method,
                        item.source_id,
                    )
                    for item in result.evidence
                    if item.value
                    == result.tax_id
                ],
            )

        print()
        print("=" * 120)
        print("FIRST-PARTY CONTACT CONTAMINATION")
        print("=" * 120)

        print(
            "own_contact_candidates:",
            len(own_contact),
        )

        for result in own_contact:
            print(
                result.candidate_id,
                "|",
                repr(result.current_name),
                "| contact:",
                repr(result.contact_name),
                "| direct:",
                result.gmail_direct_messages,
                "| relay:",
                result.gmail_relay_messages,
            )

        print()
        print("=" * 120)
        print("FIRST-PARTY ENTITY CONTAMINATION")
        print("=" * 120)

        print(
            "own_entity_candidates:",
            len(own_entity),
        )

        for result in own_entity:
            print(
                result.candidate_id,
                "|",
                repr(result.current_name),
                "| entity:",
                repr(result.entity_name),
            )

        print()
        print("=" * 120)
        print("RELAY CONTAINERS")
        print("=" * 120)

        print(
            "relay_container_count:",
            len(relay_containers),
        )

        for result in relay_containers:
            print(
                result.candidate_id,
                "|",
                repr(result.current_name),
                "| relay_messages:",
                result.gmail_relay_messages,
                "| direct_messages:",
                result.gmail_direct_messages,
                "| entity:",
                repr(result.entity_name),
                "| contact:",
                repr(result.contact_name),
            )

        print()
        print("=" * 120)
        print("CONTROL PROJECTIONS")
        print("=" * 120)

        by_id = {
            result.candidate_id: result
            for result in results
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
                "gmail_direct_messages:",
                result.gmail_direct_messages,
            )

            print(
                "gmail_relay_messages:",
                result.gmail_relay_messages,
            )

            print(
                "gmail_quoted_boundaries:",
                result.gmail_quoted_boundaries,
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

        # ====================================================
        # HARD V1.2 EXPECTATIONS
        # ====================================================

        if own_tax:
            raise RuntimeError(
                "First-party NIP contamination still "
                f"exists in {len(own_tax)} candidates."
            )

        relay_ids = {
            result.candidate_id
            for result in relay_containers
        }

        # At minimum the two known technical relay candidates
        # must be recognized as relay-bearing staging records.
        if not {
            3095,
            3344,
        }.issubset(
            {
                result.candidate_id
                for result in results
                if result.gmail_relay_messages > 0
            }
        ):
            raise RuntimeError(
                "Known relay candidates 3095/3344 "
                "were not recognized."
            )

        print()
        print("=" * 120)
        print("VALIDATION")
        print("=" * 120)

        print(
            "first-party tax contamination 0: OK"
        )

        print(
            "known relay candidates recognized: OK"
        )

        print(
            "remaining own-contact cases are intentionally "
            "deferred to First-Party Identity Registry."
        )

        print()
        print("=" * 120)
        print("SAFETY")
        print("=" * 120)

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
            "CLIENT ENTITY PROJECTION 1.2: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
