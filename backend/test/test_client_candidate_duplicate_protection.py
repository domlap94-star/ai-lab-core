from __future__ import annotations

from app.database.session import SessionLocal
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.services.client_candidate_promotion_service import (
    CandidateDuplicateClientError,
    ClientCandidatePromotionService,
)


def main() -> None:
    db = SessionLocal()

    try:
        existing_client = (
            db.query(Client)
            .filter(
                Client.deleted_at.is_(None)
            )
            .order_by(
                Client.id.asc()
            )
            .first()
        )

        if existing_client is None:
            raise RuntimeError(
                "No existing client available."
            )

        print()
        print("=" * 110)
        print("EXISTING CLIENT")
        print("=" * 110)

        print(
            "client_id:",
            existing_client.id,
        )
        print(
            "name:",
            existing_client.name,
        )
        print(
            "email:",
            existing_client.primary_email,
        )
        print(
            "phone:",
            existing_client.primary_phone,
        )
        print(
            "tax_id:",
            existing_client.tax_id,
        )

        test_email = (
            existing_client.primary_email
            or "duplicate-test@example.com"
        )

        candidate = ClientCandidate(
            client_type=(
                existing_client.client_type
                or "person"
            ),
            name="Duplicate Protection Test",
            legal_name=None,
            tax_id=None,
            registration_number=None,
            industry_id=None,
            website=None,
            primary_email=test_email,
            primary_phone=None,
            street=None,
            building_number=None,
            unit_number=None,
            postal_code=None,
            city=None,
            country_code="PL",
            notes=None,
            status="pending",
            confidence=0.9,
            matched_client_id=None,
            source_summary=(
                "duplicate protection test"
            ),
            raw_payload={
                "test": True,
            },
        )

        db.add(
            candidate
        )

        db.flush()

        if existing_client.primary_email is None:
            existing_client.primary_email = (
                test_email
            )

            db.flush()

        service = (
            ClientCandidatePromotionService(
                db
            )
        )

        print()
        print("=" * 110)
        print("DUPLICATE TEST")
        print("=" * 110)

        try:
            service.promote(
                candidate.id
            )

        except CandidateDuplicateClientError as error:
            print(
                "duplicate_detected:",
                True,
            )
            print(
                "matched_client_id:",
                error.client_id,
            )
            print(
                "matched_by:",
                error.matched_by,
            )

            if (
                error.client_id
                != existing_client.id
            ):
                raise RuntimeError(
                    "Wrong existing client matched."
                )

            if error.matched_by != "email":
                raise RuntimeError(
                    "Expected email duplicate match."
                )

        else:
            raise RuntimeError(
                "Duplicate candidate was promoted."
            )

        print()
        print(
            "DUPLICATE PROTECTION: OK"
        )

        db.rollback()

        print()
        print(
            "ROLLBACK: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
