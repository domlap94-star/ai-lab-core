from __future__ import annotations

import json

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.services.gmail_message_boundary_service import (
    GmailMessageBoundaryService,
)


CONTROL_IDS = (
    1055,
    1365,
    2535,
    2657,
    2764,
    3269,
    3305,
    3307,
    3323,
    3489,
)


def clean(value):
    if value is None:
        return ""

    return " ".join(
        str(value).strip().split()
    )


def message_text(payload):
    for key in (
        "text",
        "textPlain",
        "snippet",
    ):
        value = payload.get(key)

        if value:
            return str(value)

    return ""


def header_values(
    payload,
    key,
):
    field = payload.get(key)

    if not isinstance(field, dict):
        return []

    values = field.get("value")

    if not isinstance(values, list):
        return []

    result = []

    for item in values:
        if not isinstance(item, dict):
            continue

        result.append(
            {
                "address": item.get("address"),
                "name": item.get("name"),
            }
        )

    return result


def print_text(
    title,
    value,
    *,
    max_lines=100,
):
    print()
    print(title)

    lines = (
        value.splitlines()
        if value
        else []
    )

    if not lines:
        print("<EMPTY>")
        return

    if len(lines) <= max_lines:
        selected = lines
    else:
        half = max_lines // 2

        selected = (
            lines[:half]
            + ["... [MIDDLE OMITTED] ..."]
            + lines[-half:]
        )

    for index, line in enumerate(
        selected,
        start=1,
    ):
        print(
            f"{index:04d}: {line}"
        )


def sheet_fields(payload):
    keys = (
        "IMIĘ ",
        "IMIĘ",
        "NAZWISKO",
        "E-MAIL",
        "TELEFON",
        "NIP",
        "FIRMA",
        "NAZWA FIRMY",
    )

    result = {}

    for key in keys:
        if key not in payload:
            continue

        value = payload.get(key)

        if value not in (
            None,
            "",
        ):
            result[key] = value

    return result


def main():
    db = SessionLocal()

    try:
        boundary = (
            GmailMessageBoundaryService()
        )

        for candidate_id in CONTROL_IDS:
            candidate = (
                db.query(ClientCandidate)
                .filter(
                    ClientCandidate.id
                    == candidate_id
                )
                .first()
            )

            print()
            print("=" * 150)

            if candidate is None:
                print(
                    "CANDIDATE NOT FOUND:",
                    candidate_id,
                )
                continue

            print(
                "CANDIDATE ID:",
                candidate.id,
            )

            print(
                "NAME:",
                repr(candidate.name),
            )

            print(
                "EMAIL:",
                repr(candidate.primary_email),
            )

            print(
                "PHONE:",
                repr(candidate.primary_phone),
            )

            print(
                "TAX ID:",
                repr(candidate.tax_id),
            )

            print(
                "CURRENT TYPE:",
                repr(candidate.client_type),
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
                "SOURCE COUNT:",
                len(sources),
            )

            for source in sources:
                payload = (
                    source.raw_payload
                    or {}
                )

                print()
                print("-" * 150)

                print(
                    "SOURCE ID:",
                    source.id,
                )

                print(
                    "SOURCE TYPE:",
                    source.source_type,
                )

                if (
                    source.source_type
                    == "google_sheets_row"
                ):
                    print(
                        "SHEET FIELDS:",
                        json.dumps(
                            sheet_fields(
                                payload
                            ),
                            ensure_ascii=False,
                        ),
                    )

                    continue

                if (
                    source.source_type
                    != "gmail_message"
                ):
                    continue

                print(
                    "FROM:",
                    json.dumps(
                        header_values(
                            payload,
                            "from",
                        ),
                        ensure_ascii=False,
                    ),
                )

                print(
                    "TO:",
                    json.dumps(
                        header_values(
                            payload,
                            "to",
                        ),
                        ensure_ascii=False,
                    ),
                )

                print(
                    "CC:",
                    json.dumps(
                        header_values(
                            payload,
                            "cc",
                        ),
                        ensure_ascii=False,
                    ),
                )

                print(
                    "SUBJECT:",
                    repr(
                        payload.get(
                            "subject"
                        )
                    ),
                )

                parsed = boundary.parse(
                    message_text(
                        payload
                    )
                )

                print(
                    "BOUNDARY:",
                    repr(
                        parsed.boundary_method
                    ),
                )

                print(
                    "RELAY:",
                    repr(
                        parsed.relay_payload
                    ),
                )

                print_text(
                    "CURRENT CONTENT:",
                    parsed.current_content,
                )

        print()
        print("=" * 150)
        print("SAFETY")
        print("=" * 150)

        print(
            "DATABASE MODIFICATIONS: 0"
        )

        print(
            "CLIENT CANDIDATE WRITES: 0"
        )

        print()
        print(
            "SEMANTIC EVIDENCE INSPECTION 1.0: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
