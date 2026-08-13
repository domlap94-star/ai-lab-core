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
    657,
    725,
    1056,
    1999,
    2071,
    2190,
    2336,
    2626,
    2627,
    2630,
    2643,
    2658,
    2697,
    2747,
    2748,
    2754,
    2807,
    2842,
    2903,
    2941,
    2957,
    2971,
    3066,
    3124,
    3154,
    3269,
    3307,
    3375,
    3379,
    3452,
}


def run_unit_checks(
    resolver: CandidateIdentityGmailResolver,
) -> None:
    print()
    print("=" * 120)
    print("SIGNATURE GRAMMAR UNIT CHECKS")
    print("=" * 120)

    valid = {
        "Sabina Sztejnwald": "Sabina Sztejnwald",
        "Pozdrawiam Marcin Brochacki": "Marcin Brochacki",
        "Pozdrawiam Henryk Makowski": "Henryk Makowski",
        "Pozdrawiam Marek Pułtorak": "Marek Pułtorak",
        "Z poważaniem Anna Kowalska": "Anna Kowalska",
        "mgr inż. Ewa Więckowska": "Ewa Więckowska",
        "arch. Mateusz Glenc": "Mateusz Glenc",
    }

    for raw, expected in valid.items():
        normalized = (
            resolver._normalize_signature_candidate(
                raw
            )
        )

        accepted = (
            resolver._valid_full_person_name(
                normalized
            )
        )

        print(
            "VALID",
            repr(raw),
            "->",
            repr(normalized),
            accepted,
        )

        if normalized != expected:
            raise RuntimeError(
                f"Normalization failed: {raw!r}"
            )

        if not accepted:
            raise RuntimeError(
                f"Expected valid person: {raw!r}"
            )

    invalid = [
        "Dzień Dobry",
        "EMAIL HMI",
        "Nadzory Przeglądy",
        "Zespół Facebooka",
        "Oddział Bydgoszcz",
        "Podnoszenie Posadzek",
        "Witam Panie Wojciechu",
        "Panie Wojciechu",
        "Szanowni Państwo",
        "Kierownik Działu Technicznego",
        "Administrator Wspólnot Mieszkaniowych",
        "Dyrektor Wydziału Organizacyjnego",
        "Przedsiębiorstwo Budownictwa Ogólnego",
        "Customer Service Specialist",
        "Google Partner Premier",
    ]

    for raw in invalid:
        normalized = (
            resolver._normalize_signature_candidate(
                raw
            )
        )

        accepted = bool(
            normalized
            and resolver._valid_full_person_name(
                normalized
            )
        )

        print(
            "INVALID",
            repr(raw),
            "->",
            repr(normalized),
            accepted,
        )

        if accepted:
            raise RuntimeError(
                f"False-positive signature: {raw!r}"
            )

    text = (
        "Dzień dobry\n\n"
        "Proszę o kontakt.\n\n"
        "Pozdrawiam\n"
        "Jan Kowalski\n"
        "tel. 500 600 700\n"
    )

    names = resolver._extract_signature_names(
        text
    )

    print(
        "SIGNOFF NEXT-LINE:",
        names,
    )

    if "Jan Kowalski" not in names:
        raise RuntimeError(
            "Signoff next-line extraction failed."
        )

    quoted = (
        "Dzień dobry\n\n"
        "Pozdrawiam\n"
        "Jan Kowalski\n\n"
        "-----Original Message-----\n"
        "From: Wojciech Łapiński\n"
        "Wojciech Łapiński\n"
    )

    stripped = resolver._strip_quoted_history(
        quoted
    )

    if "Wojciech Łapiński" in stripped:
        raise RuntimeError(
            "Quoted history filtering failed."
        )

    print(
        "QUOTED HISTORY: OK"
    )

    print()
    print(
        "SIGNATURE GRAMMAR UNIT CHECKS: OK"
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

        run_unit_checks(
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

        reviews = []
        ambiguous = []

        controls = {}

        secondary_insufficient = 0

        for candidate in candidates:
            before = secondary.resolve(
                candidate
            )

            if (
                before.status
                != "insufficient"
            ):
                continue

            secondary_insufficient += 1

            after = gmail.resolve(
                candidate
            )

            counts[
                after.status
            ] += 1

            transitions[
                (
                    before.status,
                    after.status,
                )
            ] += 1

            if after.status == "review":
                reviews.append(
                    after
                )

            elif after.status == "ambiguous":
                ambiguous.append(
                    after
                )

            if candidate.id in CONTROL_IDS:
                controls[
                    candidate.id
                ] = after

        print()
        print("=" * 120)
        print("GMAIL IDENTITY LAYER 1.2 SUMMARY")
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
                "Gmail Identity Layer 1.2 "
                "must produce zero AUTO_SAFE."
            )

        print()
        print("=" * 120)
        print("TRANSITIONS")
        print("=" * 120)

        for key, count in sorted(
            transitions.items()
        ):
            print(
                f"{key[0]} -> {key[1]}:",
                count,
            )

        print()
        print("=" * 120)
        print("HIGH CONFIDENCE REVIEW >= 0.94")
        print("=" * 120)

        high = [
            result
            for result in reviews
            if result.confidence >= 0.94
        ]

        for result in high:
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
        print(
            "high_confidence_review:",
            len(high),
        )

        print()
        print("=" * 120)
        print("ALL AMBIGUOUS")
        print("=" * 120)

        for result in ambiguous:
            print()
            print(
                result.candidate_id,
                "|",
                repr(result.current_name),
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
            "GMAIL IDENTITY LAYER 1.2 DRY RUN: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
