from __future__ import annotations

import json
from collections import Counter

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate


CONTROL_CANDIDATES = {
    436,
    2061,
    2295,
    2537,
    2601,
    2772,
    2804,
    2971,
    3424,
}

CONTROL_SOURCES = {
    6582,
    5759,
    3617,
    3956,
    3007,
    3622,
    3329,
    4310,
    6447,
}


def clean(value):
    if value is None:
        return ""

    return str(value).strip()


def header_addresses(
    payload,
    field_name,
):
    field = payload.get(
        field_name
    )

    if not isinstance(
        field,
        dict,
    ):
        return []

    values = field.get(
        "value"
    )

    if not isinstance(
        values,
        list,
    ):
        return []

    result = []

    for item in values:
        if not isinstance(
            item,
            dict,
        ):
            continue

        address = clean(
            item.get("address")
        ).casefold()

        name = clean(
            item.get("name")
        )

        if address:
            result.append(
                {
                    "address": address,
                    "name": name,
                }
            )

    return result


def message_text(
    payload,
):
    for key in (
        "text",
        "textPlain",
        "snippet",
    ):
        value = payload.get(
            key
        )

        if value:
            return str(value)

    return ""


def main():
    db = SessionLocal()

    try:
        print()
        print("=" * 140)
        print("CONTROL CANDIDATES")
        print("=" * 140)

        for candidate_id in sorted(
            CONTROL_CANDIDATES
        ):
            candidate = (
                db.query(ClientCandidate)
                .filter(
                    ClientCandidate.id
                    == candidate_id
                )
                .first()
            )

            print()
            print("-" * 140)

            if candidate is None:
                print(
                    candidate_id,
                    "| NOT FOUND"
                )
                continue

            print(
                "candidate_id:",
                candidate.id,
            )

            print(
                "name:",
                repr(candidate.name),
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
                "client_type:",
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
                "source_count:",
                len(sources),
            )

            for source in sources:
                payload = (
                    source.raw_payload
                    or {}
                )

                is_control = (
                    source.id
                    in CONTROL_SOURCES
                )

                print()
                print(
                    "SOURCE",
                    source.id,
                    "| type:",
                    source.source_type,
                    "| CONTROL:",
                    is_control,
                )

                print(
                    "source_external_id:",
                    repr(
                        getattr(
                            source,
                            "source_external_id",
                            None,
                        )
                    ),
                )

                print(
                    "gmail_message_id:",
                    repr(
                        getattr(
                            source,
                            "gmail_message_id",
                            None,
                        )
                    ),
                )

                print(
                    "gmail_thread_id:",
                    repr(
                        getattr(
                            source,
                            "gmail_thread_id",
                            None,
                        )
                    ),
                )

                if (
                    source.source_type
                    == "gmail_message"
                ):
                    print(
                        "from:",
                        json.dumps(
                            header_addresses(
                                payload,
                                "from",
                            ),
                            ensure_ascii=False,
                        ),
                    )

                    print(
                        "to:",
                        json.dumps(
                            header_addresses(
                                payload,
                                "to",
                            ),
                            ensure_ascii=False,
                        ),
                    )

                    print(
                        "cc:",
                        json.dumps(
                            header_addresses(
                                payload,
                                "cc",
                            ),
                            ensure_ascii=False,
                        ),
                    )

                    print(
                        "subject:",
                        repr(
                            payload.get(
                                "subject"
                            )
                        ),
                    )

                    if is_control:
                        text = message_text(
                            payload
                        )

                        print()
                        print(
                            "CONTROL TEXT:"
                        )

                        lines = text.splitlines()

                        if len(lines) > 80:
                            lines = (
                                lines[:40]
                                + [
                                    "... [MIDDLE OMITTED] ..."
                                ]
                                + lines[-40:]
                            )

                        for index, line in enumerate(
                            lines,
                            start=1,
                        ):
                            print(
                                f"{index:04d}: {line}"
                            )

                elif (
                    source.source_type
                    == "google_sheets_row"
                ):
                    print(
                        "sheet_identity_fields:",
                    )

                    for key in (
                        "IMIĘ",
                        "IMIĘ ",
                        "NAZWISKO",
                        "E-MAIL",
                        "TELEFON",
                        "NIP",
                    ):
                        if key in payload:
                            print(
                                " ",
                                repr(key),
                                ":",
                                repr(
                                    payload.get(key)
                                ),
                            )

        print()
        print("=" * 140)
        print("CONTROL SOURCE OWNERSHIP")
        print("=" * 140)

        for source_id in sorted(
            CONTROL_SOURCES
        ):
            source = (
                db.query(CandidateSource)
                .filter(
                    CandidateSource.id
                    == source_id
                )
                .first()
            )

            if source is None:
                print(
                    source_id,
                    "| NOT FOUND"
                )
                continue

            candidate = (
                db.query(ClientCandidate)
                .filter(
                    ClientCandidate.id
                    == source.candidate_id
                )
                .first()
            )

            payload = (
                source.raw_payload
                or {}
            )

            print()
            print(
                "source_id:",
                source.id,
            )

            print(
                "candidate_id:",
                source.candidate_id,
            )

            print(
                "candidate_name:",
                repr(
                    candidate.name
                    if candidate
                    else None
                ),
            )

            print(
                "candidate_email:",
                repr(
                    candidate.primary_email
                    if candidate
                    else None
                ),
            )

            print(
                "from:",
                json.dumps(
                    header_addresses(
                        payload,
                        "from",
                    ),
                    ensure_ascii=False,
                ),
            )

            print(
                "to:",
                json.dumps(
                    header_addresses(
                        payload,
                        "to",
                    ),
                    ensure_ascii=False,
                ),
            )

            print(
                "subject:",
                repr(
                    payload.get(
                        "subject"
                    )
                ),
            )

        print()
        print("=" * 140)
        print("SAFETY")
        print("=" * 140)

        print(
            "DATABASE MODIFICATIONS: 0"
        )

        print(
            "CANDIDATE SOURCE PAIRING AUDIT 1.0: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
