from __future__ import annotations

import unicodedata
from collections import Counter

from sqlalchemy import or_

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.services.client_entity_projection_policy_service import (
    ClientEntityProjectionPolicyService,
)
from app.services.first_party_identity_registry import (
    FirstPartyIdentityRegistry,
)


CONTROL_IDS = {
    27,
    133,
    221,
    436,
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
    2772,

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


EXPECTED_EXTERNAL_TAX = {
    2285: "6912229250",
    2688: "5140120304",
    2764: "8212663873",
    2998: "6793219244",
    3269: "8341882519",
    3307: "5841352935",
    3489: "5210124745",
}


def normalize(
    value,
):
    if not value:
        return ""

    value = unicodedata.normalize(
        "NFKD",
        str(value),
    )

    value = "".join(
        character
        for character in value
        if not unicodedata.combining(
            character
        )
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


def main():
    db = SessionLocal()

    try:
        service = (
            ClientEntityProjectionPolicyService(
                db
            )
        )

        registry = (
            FirstPartyIdentityRegistry
        )

        candidates = (
            db.query(ClientCandidate)
            .filter(
                ClientCandidate.deleted_at.is_(None),
                or_(
                    ClientCandidate.status == "pending",
                    ClientCandidate.id.in_(CONTROL_IDS),
                ),
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
        own_email = []

        first_party_internal = []
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
                and registry
                .is_first_party_tax_id(
                    result.tax_id
                )
            ):
                own_tax.append(
                    result
                )

            if (
                result.contact_name
                and registry
                .is_first_party_person(
                    result.contact_name
                )
            ):
                own_contact.append(
                    result
                )

            if (
                result.entity_name
                and registry
                .is_first_party_entity(
                    result.entity_name
                )
            ):
                own_entity.append(
                    result
                )

            if (
                result.contact_email
                and registry
                .is_first_party_email(
                    result.contact_email
                )
            ):
                own_email.append(
                    result
                )

            if (
                result.status
                == "first_party_internal"
            ):
                first_party_internal.append(
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
            "CLIENT ENTITY PROJECTION 1.3 SUMMARY"
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
        print("FIRST-PARTY CONTAMINATION")
        print("=" * 120)

        print(
            "own_tax_candidates:",
            len(own_tax),
        )

        print(
            "own_contact_candidates:",
            len(own_contact),
        )

        print(
            "own_entity_candidates:",
            len(own_entity),
        )

        print(
            "own_email_candidates:",
            len(own_email),
        )

        for label, rows in (
            (
                "OWN TAX",
                own_tax,
            ),
            (
                "OWN CONTACT",
                own_contact,
            ),
            (
                "OWN ENTITY",
                own_entity,
            ),
            (
                "OWN EMAIL",
                own_email,
            ),
        ):
            for result in rows:
                print(
                    label,
                    "|",
                    result.candidate_id,
                    "|",
                    repr(
                        result.current_name
                    ),
                    "| entity:",
                    repr(
                        result.entity_name
                    ),
                    "| contact:",
                    repr(
                        result.contact_name
                    ),
                    "| email:",
                    repr(
                        result.contact_email
                    ),
                    "| tax:",
                    repr(
                        result.tax_id
                    ),
                )

        print()
        print("=" * 120)
        print("FIRST-PARTY INTERNAL")
        print("=" * 120)

        print(
            "first_party_internal_count:",
            len(first_party_internal),
        )

        for result in first_party_internal:
            print(
                result.candidate_id,
                "|",
                repr(result.current_name),
                "| status:",
                result.status,
                "| entity:",
                repr(result.entity_name),
                "| contact:",
                repr(result.contact_name),
                "| tax:",
                repr(result.tax_id),
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
                "reason:",
                repr(result.reason),
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
        # HARD FIRST-PARTY EXPECTATIONS
        # ====================================================

        if own_tax:
            raise RuntimeError(
                "First-party tax contamination "
                f"remains: {len(own_tax)}"
            )

        if own_contact:
            raise RuntimeError(
                "First-party contact contamination "
                f"remains: {len(own_contact)}"
            )

        if own_entity:
            raise RuntimeError(
                "First-party entity contamination "
                f"remains: {len(own_entity)}"
            )

        if own_email:
            raise RuntimeError(
                "First-party email contamination "
                f"remains: {len(own_email)}"
            )

        # Mariusz Lipski must remain an external person
        # while our historical NIP disappears.
        mariusz = by_id[
            436
        ]

        if mariusz.tax_id is not None:
            raise RuntimeError(
                "Candidate 436 still has a tax ID: "
                f"{mariusz.tax_id!r}"
            )

        if (
            normalize(
                mariusz.entity_name
            )
            != "mariusz lipski"
        ):
            raise RuntimeError(
                "Candidate 436 external identity "
                "was damaged: "
                f"{mariusz.entity_name!r}"
            )

        # domlap94 must not become a CRM customer.
        internal_2595 = by_id[
            2595
        ]

        if (
            internal_2595.status
            != "first_party_internal"
        ):
            raise RuntimeError(
                "Candidate 2595 expected "
                "first_party_internal, got "
                f"{internal_2595.status!r}"
            )

        if any(
            (
                internal_2595.entity_name,
                internal_2595.contact_name,
                internal_2595.tax_id,
            )
        ):
            raise RuntimeError(
                "Candidate 2595 still carries "
                "projected client identity."
            )

        # pawcioou is a first-party relay container.
        relay_3095 = by_id[
            3095
        ]

        if (
            relay_3095.status
            != "relay_container"
        ):
            raise RuntimeError(
                "Candidate 3095 expected "
                "relay_container, got "
                f"{relay_3095.status!r}"
            )

        if any(
            (
                relay_3095.entity_name,
                relay_3095.contact_name,
                relay_3095.tax_id,
            )
        ):
            raise RuntimeError(
                "Candidate 3095 still carries "
                "a projected client identity."
            )

        relay_3344 = by_id[
            3344
        ]

        if (
            relay_3344.status
            != "relay_container"
        ):
            raise RuntimeError(
                "Candidate 3344 expected "
                "relay_container, got "
                f"{relay_3344.status!r}"
            )

        # ====================================================
        # EXTERNAL DATA MUST SURVIVE
        # ====================================================

        for (
            candidate_id,
            expected_tax,
        ) in EXPECTED_EXTERNAL_TAX.items():
            result = by_id[
                candidate_id
            ]

            if (
                result.tax_id
                != expected_tax
            ):
                raise RuntimeError(
                    "External tax ID damaged for "
                    f"candidate {candidate_id}: "
                    f"expected {expected_tax!r}, "
                    f"got {result.tax_id!r}"
                )

        # Important organization/contact controls.
        if (
            by_id[2067].entity_name
            != "JBW INVEST"
        ):
            raise RuntimeError(
                "JBW INVEST entity regression."
            )

        if (
            normalize(
                by_id[2067].contact_name
            )
            != "karol walczak"
        ):
            raise RuntimeError(
                "JBW INVEST contact regression."
            )

        if (
            "polski komfort"
            not in normalize(
                by_id[2285].entity_name
            )
        ):
            raise RuntimeError(
                "Polski Komfort entity regression."
            )

        if (
            "trasko invest"
            not in normalize(
                by_id[2688].entity_name
            )
        ):
            raise RuntimeError(
                "Trasko Invest entity regression."
            )

        if (
            "tb.invest"
            not in normalize(
                by_id[3307].entity_name
            )
        ):
            raise RuntimeError(
                "TB.INVEST entity regression."
            )

        if (
            "oddzia"
            not in normalize(
                by_id[3307]
                .organizational_unit
            )
        ):
            raise RuntimeError(
                "TB.INVEST organizational "
                "unit regression."
            )

        if (
            by_id[3462].entity_type
            != "institution"
        ):
            raise RuntimeError(
                "Urząd Gminy institution "
                "classification regression."
            )

        print()
        print("=" * 120)
        print("VALIDATION")
        print("=" * 120)

        print(
            "first-party tax contamination 0: OK"
        )

        print(
            "first-party contact contamination 0: OK"
        )

        print(
            "first-party entity contamination 0: OK"
        )

        print(
            "first-party email contamination 0: OK"
        )

        print(
            "Mariusz Lipski external identity preserved: OK"
        )

        print(
            "candidate 2595 isolated as first-party: OK"
        )

        print(
            "candidate 3095 isolated as relay container: OK"
        )

        print(
            "candidate 3344 relay container preserved: OK"
        )

        print(
            "external tax IDs preserved: OK"
        )

        print(
            "Google Sheets + Gmail organization controls preserved: OK"
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
            "CLIENT ENTITY PROJECTION 1.3: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
