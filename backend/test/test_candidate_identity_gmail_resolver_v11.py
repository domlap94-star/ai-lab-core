from __future__ import annotations

from collections import Counter

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.services.candidate_identity_gmail_resolver import (
    CandidateIdentityGmailResolver,
)
from app.services.candidate_identity_secondary_resolver import (
    CandidateIdentitySecondaryResolver,
)


CONTROL_IDS = {
    41,
    657,
    725,
    1056,
    2071,
    2336,
    2583,
    2587,
    2601,
    2629,
    2643,
    2748,
    2754,
    2820,
    2842,
    2891,
    2903,
    2914,
    2932,
    2941,
    2963,
    2971,
    3050,
    3066,
    3181,
    3261,
    3262,
    3274,
    3281,
    3375,
    3429,
}


def parser_unit_checks(
    resolver: CandidateIdentityGmailResolver,
) -> None:
    print()
    print("=" * 120)
    print("STRICT PARSER UNIT CHECKS")
    print("=" * 120)

    valid = [
        "Sabina Sztejnwald",
        "Artur Sienicki",
        "Danuta Zenel",
        "Natalia Banaszak-Adamska",
        "Krzysztof Piotrowski",
        "Karolina Konkiel",
        "Maciej Rogalski",
    ]

    invalid = [
        "ochronie danych osobowych",
        "Warszawa dom szeregowy",
        "Czekam na sygnał",
        "Masz tutaj plik",
        "Potwierdzenie wykonania przelewu",
        "Kierownik Działu Technicznego",
        "Specjalista ds Zamówień",
        "Administrator Wspólnot Mieszkaniowych",
        "Przedsiębiorstwo Budownictwa Ogólnego",
        "Szanowni Państwo",
        "Sign Up Today",
        "Google Partner Premier",
    ]

    for value in valid:
        actual = resolver._valid_full_person_name(
            value
        )

        print(
            "VALID",
            repr(value),
            "->",
            actual,
        )

        if not actual:
            raise RuntimeError(
                f"Expected valid person name: {value!r}"
            )

    for value in invalid:
        actual = resolver._valid_full_person_name(
            value
        )

        print(
            "INVALID",
            repr(value),
            "->",
            actual,
        )

        if actual:
            raise RuntimeError(
                f"False-positive person name: {value!r}"
            )

    quoted = """Dzień dobry

W załączeniu dokumentacja.

Sabina Sztejnwald
tel. 500 600 700

-----Original Message-----
From: Wojciech Łapiński
Wojciech Łapiński
"""

    stripped = resolver._strip_quoted_history(
        quoted
    )

    print()
    print(
        "QUOTED HISTORY RESULT:",
        repr(stripped),
    )

    if "Wojciech Łapiński" in stripped:
        raise RuntimeError(
            "Quoted history was not removed."
        )

    if "Sabina Sztejnwald" not in stripped:
        raise RuntimeError(
            "Newest message signature was removed."
        )

    salutations = (
        resolver._extract_salutation_vocatives(
            "Panie Arturze,\n"
            "proszę o kontakt."
        )
    )

    print(
        "VOCATIVE TEST:",
        salutations,
    )

    if salutations != ["Arturze"]:
        raise RuntimeError(
            "Vocative extraction failed."
        )

    print()
    print(
        "STRICT PARSER UNIT CHECKS: OK"
    )


def main() -> None:
    db = SessionLocal()

    try:
        secondary = (
            CandidateIdentitySecondaryResolver(
                db
            )
        )

        gmail = CandidateIdentityGmailResolver(
            db
        )

        parser_unit_checks(
            gmail
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

        counts = Counter()
        transitions = Counter()

        results = {
            "auto_safe": [],
            "review": [],
            "ambiguous": [],
            "insufficient": [],
        }

        secondary_insufficient = 0

        controls = {}

        for candidate in candidates:
            before = secondary.resolve(
                candidate
            )

            if before.status != "insufficient":
                continue

            secondary_insufficient += 1

            after = gmail.resolve(
                candidate
            )

            counts[after.status] += 1

            transitions[
                (
                    before.status,
                    after.status,
                )
            ] += 1

            results[
                after.status
            ].append(
                after
            )

            if candidate.id in CONTROL_IDS:
                controls[
                    candidate.id
                ] = after

        print()
        print("=" * 120)
        print("GMAIL IDENTITY LAYER 1.1 SUMMARY")
        print("=" * 120)

        print(
            "secondary_insufficient:",
            secondary_insufficient,
        )

        for status in (
            "auto_safe",
            "review",
            "ambiguous",
            "insufficient",
        ):
            print(
                f"{status}:",
                counts[status],
            )

        if counts["auto_safe"] != 0:
            raise RuntimeError(
                "Gmail Layer 1.1 must not produce AUTO_SAFE."
            )

        print()
        print("=" * 120)
        print("TRANSITIONS")
        print("=" * 120)

        for transition, count in sorted(
            transitions.items()
        ):
            print(
                f"{transition[0]} -> {transition[1]}:",
                count,
            )

        print()
        print("=" * 120)
        print("ALL REVIEW RESULTS")
        print("=" * 120)

        for result in results["review"]:
            print()
            print(
                result.candidate_id,
                "|",
                repr(result.current_name),
                "->",
                repr(result.proposed_name),
                "|",
                result.confidence,
            )

            print(
                "reason:",
                result.reason,
            )

            for evidence in result.evidence:
                if evidence.method.startswith(
                    "gmail_"
                ):
                    print(
                        "  ",
                        evidence.method,
                        "|",
                        repr(evidence.value),
                        "| source",
                        evidence.source_id,
                    )

        print()
        print("=" * 120)
        print("ALL AMBIGUOUS RESULTS")
        print("=" * 120)

        for result in results["ambiguous"]:
            print()
            print(
                result.candidate_id,
                "|",
                repr(result.current_name),
            )

            print(
                "reason:",
                result.reason,
            )

            for evidence in result.evidence:
                if evidence.method.startswith(
                    "gmail_"
                ):
                    print(
                        "  ",
                        evidence.method,
                        "|",
                        repr(evidence.value),
                        "| source",
                        evidence.source_id,
                    )

        print()
        print("=" * 120)
        print("CONTROL CANDIDATES")
        print("=" * 120)

        for candidate_id in sorted(
            CONTROL_IDS
        ):
            result = controls.get(
                candidate_id
            )

            print()

            if result is None:
                print(
                    candidate_id,
                    "| NOT SECONDARY-INSUFFICIENT",
                )
                continue

            print(
                "candidate_id:",
                candidate_id,
            )

            print(
                "current_name:",
                repr(result.current_name),
            )

            print(
                "status:",
                result.status,
            )

            print(
                "proposed_name:",
                repr(result.proposed_name),
            )

            print(
                "confidence:",
                result.confidence,
            )

            print(
                "reason:",
                result.reason,
            )

            for evidence in result.evidence:
                if evidence.method.startswith(
                    "gmail_"
                ):
                    print(
                        "  evidence:",
                        evidence.method,
                        "|",
                        repr(evidence.value),
                        "| source",
                        evidence.source_id,
                    )

        print()
        print("=" * 120)
        print("DATABASE NOT MODIFIED")
        print("=" * 120)

        print()
        print(
            "GMAIL IDENTITY LAYER 1.1 DRY RUN: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
