from __future__ import annotations

from collections import Counter

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.services.candidate_identity_resolver import (
    CandidateIdentityResolver,
)


IMPORTANT_IDS = {
    2,
    3,
    4,
    6,
    8,
    10,
    12,
    13,
    23,
    27,
    32,
}


def main() -> None:
    db = SessionLocal()

    try:
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

        resolver = CandidateIdentityResolver(
            db
        )

        counts = Counter()
        important = []

        auto_samples = []
        ambiguous_samples = []
        insufficient_samples = []

        for candidate in candidates:
            result = resolver.resolve(
                candidate
            )

            counts[result.status] += 1

            if candidate.id in IMPORTANT_IDS:
                important.append(
                    result
                )

            if (
                result.status == "auto_safe"
                and len(auto_samples) < 20
            ):
                auto_samples.append(
                    result
                )

            if (
                result.status == "ambiguous"
                and len(ambiguous_samples) < 20
            ):
                ambiguous_samples.append(
                    result
                )

            if (
                result.status == "insufficient"
                and len(insufficient_samples) < 20
            ):
                insufficient_samples.append(
                    result
                )

        print()
        print("=" * 120)
        print("CANDIDATE IDENTITY RESOLVER 1.0")
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
        print("IMPORTANT CANDIDATES")
        print("=" * 120)

        for result in important:
            print()
            print(
                "candidate_id:",
                result.candidate_id,
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

            for evidence in result.evidence:
                print(
                    "  evidence:",
                    evidence.method,
                    "|",
                    evidence.value,
                    "| source",
                    evidence.source_id,
                )

        def print_group(
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

        print_group(
            "AUTO SAFE SAMPLES",
            auto_samples,
        )

        print_group(
            "AMBIGUOUS SAMPLES",
            ambiguous_samples,
        )

        print_group(
            "INSUFFICIENT SAMPLES",
            insufficient_samples,
        )

        print()
        print("=" * 120)
        print("DRY RUN COMPLETE - DATABASE NOT MODIFIED")
        print("=" * 120)

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
