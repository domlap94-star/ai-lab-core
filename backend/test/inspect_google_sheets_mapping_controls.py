from __future__ import annotations

import json

from sqlalchemy import text

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate


CONTROL_IDS = (
    2067,  # JBW INVEST / Karol Walczak
    2236,  # MAXTECH / Grzegorz Stachowiak
    2285,  # Polski Komfort / Ewelina Rogińska
    2331,  # OPTEX / Jacek Gorzeń
    2688,  # Trasko Invest
    2764,  # Emer Bud
    2998,  # ETENDI
    3269,  # Powiat Łowicki
    3307,  # TBI Invest
    3474,  # BOWIM
)


def main() -> None:
    db = SessionLocal()

    try:
        print()
        print("=" * 120)
        print("CHECK CONSTRAINT DEFINITIONS")
        print("=" * 120)

        rows = db.execute(
            text(
                """
                SELECT
                    conname,
                    pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conname IN (
                    'ck_clients_client_type',
                    'ck_client_candidates_client_type'
                )
                ORDER BY conname
                """
            )
        ).all()

        for name, definition in rows:
            print(
                name,
                "=",
                definition,
            )

        print()
        print("=" * 120)
        print("CONTROL CANDIDATES + SHEET RAW FIELDS")
        print("=" * 120)

        for candidate_id in CONTROL_IDS:
            candidate = (
                db.query(ClientCandidate)
                .filter(
                    ClientCandidate.id == candidate_id
                )
                .first()
            )

            if candidate is None:
                print()
                print(
                    candidate_id,
                    "| NOT FOUND"
                )
                continue

            print()
            print("-" * 120)
            print(
                "candidate_id:",
                candidate.id,
            )
            print(
                "current_name:",
                repr(candidate.name),
            )
            print(
                "current_type:",
                repr(candidate.client_type),
            )
            print(
                "legal_name:",
                repr(candidate.legal_name),
            )
            print(
                "email:",
                repr(candidate.primary_email),
            )
            print(
                "phone:",
                repr(candidate.primary_phone),
            )

            sources = (
                db.query(CandidateSource)
                .filter(
                    CandidateSource.candidate_id
                    == candidate_id,
                    CandidateSource.source_type
                    == "google_sheets_row",
                    CandidateSource.deleted_at.is_(None),
                )
                .order_by(
                    CandidateSource.id.asc()
                )
                .all()
            )

            for source in sources:
                payload = source.raw_payload or {}

                print()
                print(
                    "source_id:",
                    source.id,
                )

                selected = {
                    key: payload.get(key)
                    for key in (
                        "IMIĘ ",
                        "IMIĘ",
                        "NAZWISKO",
                        "E-MAIL",
                        "TELEFON",
                        "ADRES",
                        "NOTATKA Z ROZMOWY",
                        "DATA NASTEPNEGO KONTAKTU",
                        "STATUS",
                    )
                    if key in payload
                }

                print(
                    json.dumps(
                        selected,
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    )
                )

        print()
        print("=" * 120)
        print("DATABASE NOT MODIFIED")
        print("=" * 120)

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
