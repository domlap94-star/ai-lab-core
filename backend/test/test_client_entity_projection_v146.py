from __future__ import annotations

import re
import unicodedata

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.services.client_entity_semantic_projection_service import (
    ClientEntitySemanticProjectionService,
)


CONTROL_IDS = (
    2535,
    2657,
    2764,
    2867,
    2933,
    3269,
    3307,
    3353,
    3462,
    3489,
    416,
    1288,
    1382,
    2189,
    2331,
    2668,
    2703,
    3360,
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

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return " ".join(value.split())


def main():
    db = SessionLocal()

    try:
        service = ClientEntitySemanticProjectionService(db)

        candidates = (
            db.query(ClientCandidate)
            .filter(
                ClientCandidate.id.in_(CONTROL_IDS)
            )
            .order_by(ClientCandidate.id.asc())
            .all()
        )

        results = {
            candidate.id: service.project(candidate)
            for candidate in candidates
        }

        print()
        print("=" * 140)
        print("CLIENT ENTITY PROJECTION 1.4.6")
        print("=" * 140)

        for candidate_id in CONTROL_IDS:
            result = results.get(candidate_id)

            if result is None:
                print()
                print("candidate_id:", candidate_id, "NOT FOUND")
                continue

            print()
            print("-" * 140)
            print("candidate_id:", candidate_id)
            print("entity:", repr(result.entity_name))
            print("type:", result.entity_type)
            print("units:", result.organizational_units)
            print("contacts:")

            for contact in result.contacts:
                print(
                    "  ",
                    repr(contact.name),
                    "| role:", repr(contact.role),
                    "| email:", repr(contact.email),
                    "| phone:", repr(contact.phone),
                    "| sources:", contact.source_ids,
                )

        # ----------------------------------------------------
        # 3353: public body must come from actual signature name,
        # not the sentence containing gmina@checiny.pl.
        # ----------------------------------------------------

        result = results[3353]
        entity = normalize(result.entity_name)

        if "urzad gminy i miasta" not in entity:
            raise RuntimeError(
                "3353: Urzad Gminy i Miasta Chęciny not selected."
            )

        if "oferte na ww prace" in entity:
            raise RuntimeError(
                "3353: offer-body sentence remains as public entity."
            )

        # ----------------------------------------------------
        # Scalar phone policy:
        # exactly one valid 9-digit number survives;
        # multi-number / placeholder values become None.
        # ----------------------------------------------------

        for candidate_id in (
            416,
            1288,
            1382,
            2189,
            2331,
        ):
            result = results[candidate_id]

            for contact in result.contacts:
                phone = contact.phone

                if not phone:
                    continue

                digits = re.sub(r"\D", "", phone)

                if len(digits) != 9:
                    raise RuntimeError(
                        f"{candidate_id}: non-scalar phone survived: {phone!r}"
                    )

        # ----------------------------------------------------
        # Academic/professional title is not CRM role.
        # ----------------------------------------------------

        result = results[3462]

        marek = [
            contact
            for contact in result.contacts
            if "marek pieniadz" in normalize(contact.name)
        ]

        if len(marek) != 1:
            raise RuntimeError(
                "3462: Marek Pieniadz contact missing or duplicated."
            )

        if marek[0].role is not None:
            raise RuntimeError(
                "3462: academic title still stored as CRM role."
            )

        # ----------------------------------------------------
        # Conservative same-person dedupe by same e-mail.
        # ----------------------------------------------------

        for candidate_id, expected_name in (
            (2668, "marcin peek"),
            (2703, "andrzej dabkowski"),
            (3360, "jakub czarnecki"),
        ):
            result = results[candidate_id]
            matching = [
                contact
                for contact in result.contacts
                if all(
                    token in normalize(contact.name)
                    for token in expected_name.split()
                )
            ]

            if len(matching) != 1:
                raise RuntimeError(
                    f"{candidate_id}: reversed-name duplicate remains."
                )

        # ----------------------------------------------------
        # True multi-contact survives.
        # ----------------------------------------------------

        result = results[2535]
        names = {
            normalize(contact.name)
            for contact in result.contacts
        }

        if not any("adrian cichon" in name for name in names):
            raise RuntimeError("2535: Adrian Cichon missing.")

        if not any("zofia deliga" in name for name in names):
            raise RuntimeError("2535: Zofia Deliga missing.")

        if len(result.contacts) < 2:
            raise RuntimeError(
                "2535: true EKO-BUD multi-contact was collapsed."
            )

        # ----------------------------------------------------
        # Core organization controls remain intact.
        # ----------------------------------------------------

        controls = {
            2657: "doraco",
            2764: "emer build",
            2867: "arcelormittal",
            2933: "weber",
            3269: "starostwo powiatowe",
            3307: "tb invest",
            3489: "winda warszawa",
        }

        for candidate_id, expected in controls.items():
            if expected not in normalize(results[candidate_id].entity_name):
                raise RuntimeError(
                    f"{candidate_id}: core entity regression: {expected}."
                )

        print()
        print("=" * 140)
        print("VALIDATION")
        print("=" * 140)
        print("public-body signature grammar: OK")
        print("scalar phone hygiene: OK")
        print("title vs role separation: OK")
        print("conservative same-person dedupe: OK")
        print("true multi-contact preservation: OK")
        print("core entity regressions: OK")
        print()
        print("DATABASE MODIFICATIONS: 0")
        print("CLIENT CANDIDATE WRITES: 0")
        print("AUTO PROMOTIONS: 0")
        print()
        print("CLIENT ENTITY PROJECTION 1.4.6: OK")

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
