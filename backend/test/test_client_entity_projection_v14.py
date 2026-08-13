from __future__ import annotations

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.services.client_entity_semantic_projection_service import (
    ClientEntitySemanticProjectionService,
)


CONTROL_IDS = (
    2535,
    2657,
    2764,
    3269,
    3305,
    3307,
    3323,
    3462,
    3489,
)


def normalize(value):
    if not value:
        return ""

    return " ".join(
        str(value)
        .casefold()
        .split()
    )


def contact_names(
    result,
):
    return {
        normalize(
            contact.name
        )
        for contact
        in result.contacts
    }


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
                ClientCandidate.id.in_(
                    CONTROL_IDS
                )
            )
            .order_by(
                ClientCandidate.id.asc()
            )
            .all()
        )

        results = {}

        print()
        print("=" * 130)
        print(
            "CLIENT ENTITY PROJECTION 1.4"
        )
        print("=" * 130)

        for candidate in candidates:
            result = service.project(
                candidate
            )

            results[
                candidate.id
            ] = result

            print()
            print("-" * 130)

            print(
                "candidate_id:",
                candidate.id,
            )

            print(
                "current_name:",
                repr(
                    candidate.name
                ),
            )

            print(
                "entity_name:",
                repr(
                    result.entity_name
                ),
            )

            print(
                "entity_type:",
                result.entity_type,
            )

            print(
                "tax_id:",
                repr(
                    result.tax_id
                ),
            )

            print(
                "organizational_units:",
                result.organizational_units,
            )

            print(
                "compatibility_unit:",
                repr(
                    result.organizational_unit
                ),
            )

            print(
                "contacts:"
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
                    "| confidence:",
                    contact.confidence,
                    "| sources:",
                    contact.source_ids,
                )

        # ====================================================
        # 2764 - EMER BUILD
        # ====================================================

        result = results[
            2764
        ]

        if (
            "emer build"
            not in normalize(
                result.entity_name
            )
        ):
            raise RuntimeError(
                "2764: EMER BUILD entity "
                "was not recovered."
            )

        if (
            result.entity_type
            != "company"
        ):
            raise RuntimeError(
                "2764: EMER BUILD must be company."
            )

        if (
            "sylwester zieńczuk"
            not in contact_names(
                result
            )
            and
            "sylwester zienczuk"
            not in contact_names(
                result
            )
        ):
            raise RuntimeError(
                "2764: Sylwester contact missing."
            )

        # ====================================================
        # 3269 - STAROSTWO / JAROSLAW
        # ====================================================

        result = results[
            3269
        ]

        if (
            result.entity_type
            != "institution"
        ):
            raise RuntimeError(
                "3269: institution regression."
            )

        if not any(
            "jaros" in name
            and "burzykowski" in name
            for name in contact_names(
                result
            )
        ):
            raise RuntimeError(
                "3269: Jaroslaw Burzykowski "
                "contact missing."
            )

        # ====================================================
        # 3307 - TB.INVEST / JACEK / ODDZIAL
        # ====================================================

        result = results[
            3307
        ]

        if (
            "tb.invest"
            not in normalize(
                result.entity_name
            )
        ):
            raise RuntimeError(
                "3307: TB.INVEST entity regression."
            )

        if not any(
            "jacek" in name
            and "barzy" in name
            for name in contact_names(
                result
            )
        ):
            raise RuntimeError(
                "3307: Jacek Barzynski "
                "contact missing."
            )

        if not any(
            "oddzia" in normalize(unit)
            and "bydgoszcz"
            in normalize(unit)
            for unit
            in result.organizational_units
        ):
            raise RuntimeError(
                "3307: Oddzial Bydgoszcz missing."
            )

        # ====================================================
        # 2657 / 3323 / 3489 - COURT METADATA
        # ====================================================

        for candidate_id in (
            2657,
            3323,
            3489,
        ):
            result = results[
                candidate_id
            ]

            bad_units = [
                unit
                for unit
                in result.organizational_units
                if "gospodarczy"
                in normalize(unit)
            ]

            if bad_units:
                raise RuntimeError(
                    f"{candidate_id}: court/KRS "
                    f"unit leakage remains: "
                    f"{bad_units}"
                )

            if (
                result.organizational_unit
                and "gospodarczy"
                in normalize(
                    result.organizational_unit
                )
            ):
                raise RuntimeError(
                    f"{candidate_id}: compatibility "
                    "court unit leakage remains."
                )

        # ====================================================
        # 2535 - EKO-BUD MULTI-CONTACT
        # ====================================================

        result = results[
            2535
        ]

        names = contact_names(
            result
        )

        if not any(
            "adrian" in name
            and "cicho" in name
            for name in names
        ):
            raise RuntimeError(
                "2535: Adrian Cichon contact missing."
            )

        if not any(
            "zofia" in name
            and "deliga" in name
            for name in names
        ):
            raise RuntimeError(
                "2535: Zofia Deliga contact missing."
            )

        # ====================================================
        # 3462 - TRUE UNIT MUST SURVIVE
        # ====================================================

        result = results[
            3462
        ]

        if not any(
            "wydzia" in normalize(unit)
            and "infrastruktury"
            in normalize(unit)
            for unit
            in result.organizational_units
        ):
            raise RuntimeError(
                "3462: legitimate department "
                "was removed."
            )

        print()
        print("=" * 130)
        print("VALIDATION")
        print("=" * 130)

        print(
            "EMER BUILD entity/contact split: OK"
        )

        print(
            "Starostwo contact recovery: OK"
        )

        print(
            "TB.INVEST contact + branch recovery: OK"
        )

        print(
            "court/KRS organizational units removed: OK"
        )

        print(
            "EKO-BUD multi-contact projection: OK"
        )

        print(
            "legitimate organizational unit preserved: OK"
        )

        print()
        print("=" * 130)
        print("SAFETY")
        print("=" * 130)

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
            "CLIENT ENTITY PROJECTION 1.4: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
