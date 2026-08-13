from __future__ import annotations

from collections import Counter

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.services.candidate_identity_secondary_resolver import (
    CandidateIdentitySecondaryResolver,
)


IMPORTANT_IDS = {
    6,
    13,
    32,
    79,
    196,
    316,
    407,
    583,
    1056,
    1465,
    1470,
}


EXPECTED = {
    6: ("review", "Aleksandra Gawdzis"),
    13: ("review", "Joanna Szulc"),
    32: ("review", "Grzegorz Szarbsko"),
    79: ("review", "Marta Czarska"),

    196: ("insufficient", None),
    407: ("insufficient", None),

    316: ("auto_safe", "Dariusz Baboń"),
    1465: ("auto_safe", "Światosław Milew"),
    1470: ("auto_safe", "Anna Wnorowska"),

    1056: ("insufficient", None),
}


def main() -> None:
    db = SessionLocal()

    try:
        resolver = (
            CandidateIdentitySecondaryResolver(
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

        counts = Counter()

        important_results = {}

        review_samples = []
        auto_samples = []
        insufficient_samples = []

        for candidate in candidates:
            result = resolver.resolve(
                candidate
            )

            counts[result.status] += 1

            if candidate.id in IMPORTANT_IDS:
                important_results[
                    candidate.id
                ] = result

            if (
                result.status == "review"
                and len(review_samples) < 30
            ):
                review_samples.append(
                    result
                )

            if (
                result.status == "auto_safe"
                and len(auto_samples) < 30
            ):
                auto_samples.append(
                    result
                )

            if (
                result.status == "insufficient"
                and len(insufficient_samples) < 30
            ):
                insufficient_samples.append(
                    result
                )

        print()
        print("=" * 120)
        print(
            "SECONDARY IDENTITY RESOLVER 1.1"
        )
        print("=" * 120)

        print(
            "pending_candidates:",
            len(candidates),
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

        print()
        print("=" * 120)
        print("CONTROL CANDIDATES")
        print("=" * 120)

        for candidate_id in sorted(
            IMPORTANT_IDS
        ):
            result = important_results[
                candidate_id
            ]

            print()
            print(
                "candidate_id:",
                candidate_id,
            )
            print(
                "current_name:",
                result.current_name,
            )
            print(
                "status:",
                result.status,
            )
            print(
                "proposed_name:",
                result.proposed_name,
            )
            print(
                "confidence:",
                result.confidence,
            )
            print(
                "reason:",
                result.reason,
            )

        print()
        print("=" * 120)
        print("EXPECTATION CHECKS")
        print("=" * 120)

        for candidate_id, expected in EXPECTED.items():
            result = important_results[
                candidate_id
            ]

            expected_status = expected[0]
            expected_name = expected[1]

            if result.status != expected_status:
                raise RuntimeError(
                    f"Candidate {candidate_id}: "
                    f"expected status "
                    f"{expected_status!r}, "
                    f"got {result.status!r}"
                )

            if (
                expected_name is not None
                and result.proposed_name
                != expected_name
            ):
                raise RuntimeError(
                    f"Candidate {candidate_id}: "
                    f"expected name "
                    f"{expected_name!r}, "
                    f"got "
                    f"{result.proposed_name!r}"
                )

            if (
                expected_name is None
                and expected_status
                == "insufficient"
                and result.proposed_name
                not in (
                    None,
                    "",
                    result.proposed_name,
                )
            ):
                raise RuntimeError(
                    "Unexpected proposal."
                )

            print(
                candidate_id,
                ": OK",
            )

        def show(
            title,
            values,
        ):
            print()
            print("=" * 120)
            print(title)
            print("=" * 120)

            for result in values:
                print(
                    result.candidate_id,
                    "|",
                    result.current_name,
                    "->",
                    result.proposed_name,
                    "|",
                    result.status,
                    "|",
                    result.confidence,
                )

        show(
            "AUTO SAFE SAMPLES",
            auto_samples,
        )

        show(
            "REVIEW SAMPLES",
            review_samples,
        )

        show(
            "INSUFFICIENT SAMPLES",
            insufficient_samples,
        )

        print()
        print("=" * 120)
        print(
            "SECONDARY RESOLVER 1.1 DRY RUN: OK"
        )
        print("=" * 120)

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
