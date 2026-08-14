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
    2,
    3,
    8,
    10,
    24,
    36,
    53,
    68,
    74,
    85,
    100,
    1056,
}


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

        secondary_insufficient = 0

        gmail_counts = Counter()

        transitions = Counter()

        auto_safe_results = []
        review_results = []
        ambiguous_results = []

        control_results = {}

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

            gmail_counts[
                after.status
            ] += 1

            transitions[
                (
                    before.status,
                    after.status,
                )
            ] += 1

            if candidate.id in CONTROL_IDS:
                control_results[
                    candidate.id
                ] = after

            if (
                after.status == "auto_safe"
            ):
                auto_safe_results.append(
                    after
                )

            elif (
                after.status == "review"
            ):
                review_results.append(
                    after
                )

            elif (
                after.status == "ambiguous"
            ):
                ambiguous_results.append(
                    after
                )

        print()
        print("=" * 120)
        print("GMAIL IDENTITY LAYER 1.0")
        print("=" * 120)

        print(
            "secondary_insufficient:",
            secondary_insufficient,
        )

        print()
        print("RESULTS WITHIN SECONDARY INSUFFICIENT:")

        for status in (
            "auto_safe",
            "review",
            "ambiguous",
            "insufficient",
        ):
            print(
                f"{status}:",
                gmail_counts[status],
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
        print("AUTO_SAFE RESULTS")
        print("=" * 120)

        for result in auto_safe_results:
            print()
            print(
                result.candidate_id,
                "|",
                repr(
                    result.current_name
                ),
                "->",
                repr(
                    result.proposed_name
                ),
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
                        repr(
                            evidence.value
                        ),
                        "| source",
                        evidence.source_id,
                    )

        print()
        print("=" * 120)
        print("REVIEW RESULTS - FIRST 100")
        print("=" * 120)

        for result in review_results[:100]:
            print()
            print(
                result.candidate_id,
                "|",
                repr(
                    result.current_name
                ),
                "->",
                repr(
                    result.proposed_name
                ),
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
                        repr(
                            evidence.value
                        ),
                        "| source",
                        evidence.source_id,
                    )

        print()
        print("=" * 120)
        print("AMBIGUOUS RESULTS - FIRST 50")
        print("=" * 120)

        for result in ambiguous_results[:50]:
            print()
            print(
                result.candidate_id,
                "|",
                repr(
                    result.current_name
                ),
                "|",
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
                        repr(
                            evidence.value
                        ),
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
            result = control_results.get(
                candidate_id
            )

            if result is None:
                print()
                print(
                    candidate_id,
                    "| NOT SECONDARY-INSUFFICIENT",
                )
                continue

            print()
            print(
                "candidate_id:",
                candidate_id,
            )

            print(
                "current_name:",
                repr(
                    result.current_name
                ),
            )

            print(
                "status:",
                result.status,
            )

            print(
                "proposed_name:",
                repr(
                    result.proposed_name
                ),
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
                        repr(
                            evidence.value
                        ),
                        "| source",
                        evidence.source_id,
                    )

        print()
        print("=" * 120)
        print("DATABASE NOT MODIFIED")
        print("=" * 120)

        print()
        print(
            "GMAIL IDENTITY LAYER 1.0 DRY RUN: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
