from __future__ import annotations

from app.database.session import SessionLocal
from app.models.client_candidate import ClientCandidate
from app.services.candidate_identity_enrichment_service import (
    CandidateIdentityEnrichmentService,
)


def main() -> None:
    db = SessionLocal()

    try:
        service = CandidateIdentityEnrichmentService(db)

        changes = service.build_auto_safe_changes()

        print()
        print("=" * 120)
        print("AUTO-SAFE IDENTITY CHANGES")
        print("=" * 120)

        print(
            "planned_changes:",
            len(changes),
        )

        if not changes:
            raise RuntimeError(
                "No AUTO_SAFE identity changes found."
            )

        before = {
            change.candidate_id: change.old_name
            for change in changes
        }

        for change in changes[:30]:
            print(
                change.candidate_id,
                "|",
                change.old_name,
                "->",
                change.new_name,
                "|",
                change.confidence,
            )

        applied = service.apply_auto_safe()

        print()
        print(
            "applied_in_transaction:",
            len(applied),
        )

        if len(applied) != len(changes):
            raise RuntimeError(
                "Applied change count does not match planned count."
            )

        for change in changes:
            candidate = (
                db.query(ClientCandidate)
                .filter(
                    ClientCandidate.id == change.candidate_id
                )
                .one()
            )

            if candidate.name != change.new_name:
                raise RuntimeError(
                    "Candidate "
                    f"{change.candidate_id} "
                    "was not updated correctly."
                )

        print()
        print("IN-TRANSACTION VALIDATION: OK")

        db.rollback()

        print()
        print("=" * 120)
        print("ROLLBACK VALIDATION")
        print("=" * 120)

        for candidate_id, original_name in before.items():
            candidate = (
                db.query(ClientCandidate)
                .filter(
                    ClientCandidate.id == candidate_id
                )
                .one()
            )

            if candidate.name != original_name:
                raise RuntimeError(
                    "Rollback failed for candidate "
                    f"{candidate_id}: "
                    f"{candidate.name!r} != "
                    f"{original_name!r}"
                )

        print(
            "rollback_restored:",
            len(before),
        )

        print("ROLLBACK VALIDATION: OK")

        print()
        print("=" * 120)
        print(
            "AUTO-SAFE IDENTITY APPLY ROLLBACK TEST: OK"
        )
        print("=" * 120)

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
