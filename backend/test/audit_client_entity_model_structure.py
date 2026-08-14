from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import inspect

from app.database.session import SessionLocal
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.candidate_source import CandidateSource


CONTROL_IDS = {
    2067,  # JBW INVEST
    2285,  # Polski Komfort Sp. z o.o.
    2331,  # OPTEX S.A.
    2688,  # Trasko Invest / Łukasz Bednarek
    2764,  # Emer Bud, Sylwester Zieńczuk
    2772,  # Projekt Budowa Sp. z o.o.
    2998,  # Biuro Rachunkowe ETENDI
    3154,  # Krzysztof Kędzierski Roll s.c.
    3269,  # powiatlowicki
    3307,  # TBI Invest
    3474,  # BOWIM S.A.
    3489,  # Winda - Warszawa Sp. z o.o.
    3507,  # Torre Construction
    3514,  # Invest Complex
    3521,  # Brochacki Domy
}


def print_model(model) -> None:
    mapper = inspect(model)

    print()
    print("=" * 120)
    print(f"MODEL: {model.__name__}")
    print("=" * 120)

    print("TABLE:", mapper.local_table.name)

    print()
    print("COLUMNS:")

    for column in mapper.local_table.columns:
        print(
            column.name,
            "| type:",
            repr(column.type),
            "| nullable:",
            column.nullable,
            "| default:",
            repr(column.default),
            "| server_default:",
            repr(column.server_default),
        )

    print()
    print("CONSTRAINTS:")

    for constraint in mapper.local_table.constraints:
        print(
            type(constraint).__name__,
            "|",
            str(constraint),
        )


def compact_payload(payload):
    if not isinstance(payload, dict):
        return payload

    keys = (
        "name",
        "first_name",
        "last_name",
        "company",
        "company_name",
        "organization",
        "legal_name",
        "client_type",
        "email",
        "phone",
        "address",
        "city",
        "nip",
        "tax_id",
        "from",
        "to",
        "cc",
        "subject",
        "snippet",
        "text",
        "textPlain",
    )

    result = {}

    for key in keys:
        if key in payload:
            value = payload[key]

            if isinstance(value, str) and len(value) > 500:
                value = value[:500] + "..."

            result[key] = value

    if result:
        return result

    # If none of the expected keys were present, expose
    # top-level structure without dumping huge bodies.
    for key, value in list(payload.items())[:30]:
        if isinstance(value, str) and len(value) > 300:
            value = value[:300] + "..."

        result[key] = value

    return result


def main() -> None:
    db = SessionLocal()

    try:
        print_model(Client)
        print_model(ClientCandidate)

        print()
        print("=" * 120)
        print("CONTROL CANDIDATES")
        print("=" * 120)

        candidates = (
            db.query(ClientCandidate)
            .filter(
                ClientCandidate.id.in_(CONTROL_IDS),
                ClientCandidate.deleted_at.is_(None),
            )
            .order_by(
                ClientCandidate.id.asc()
            )
            .all()
        )

        for candidate in candidates:
            print()
            print("-" * 120)
            print(
                "candidate_id:",
                candidate.id,
            )
            print(
                "name:",
                repr(candidate.name),
            )
            print(
                "legal_name:",
                repr(candidate.legal_name),
            )
            print(
                "client_type:",
                repr(candidate.client_type),
            )
            print(
                "email:",
                repr(candidate.primary_email),
            )
            print(
                "phone:",
                repr(candidate.primary_phone),
            )
            print(
                "tax_id:",
                repr(candidate.tax_id),
            )
            print(
                "city:",
                repr(candidate.city),
            )

            sources = (
                db.query(CandidateSource)
                .filter(
                    CandidateSource.candidate_id
                    == candidate.id,
                    CandidateSource.deleted_at.is_(None),
                )
                .order_by(
                    CandidateSource.id.asc()
                )
                .all()
            )

            print(
                "sources:",
                len(sources),
            )

            for source in sources:
                print()
                print(
                    "  SOURCE",
                    source.id,
                    "|",
                    source.source_type,
                )

                payload = compact_payload(
                    source.raw_payload or {}
                )

                print(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        indent=4,
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
