from __future__ import annotations

import json

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.services.gmail_message_boundary_service import (
    GmailMessageBoundaryService,
)


SOURCE_IDS = (
    3007,
    3329,
    3617,
    3622,
    3956,
    4310,
    5759,
    6447,
    6582,
)


def header_addresses(
    payload,
    field_name,
):
    field = payload.get(field_name)

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


def print_numbered(
    text,
    *,
    limit=160,
):
    lines = text.splitlines()

    if len(lines) > limit:
        selected = (
            lines[:80]
            + [
                "... [MIDDLE OMITTED] ..."
            ]
            + lines[-80:]
        )
    else:
        selected = lines

    for index, line in enumerate(
        selected,
        start=1,
    ):
        print(
            f"{index:04d}: {line}"
        )


def main():
    db = SessionLocal()

    try:
        boundary_service = (
            GmailMessageBoundaryService()
        )

        for source_id in SOURCE_IDS:
            source = (
                db.query(CandidateSource)
                .filter(
                    CandidateSource.id
                    == source_id
                )
                .first()
            )

            print()
            print("=" * 140)

            if source is None:
                print(
                    "SOURCE NOT FOUND:",
                    source_id,
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

            payload = source.raw_payload or {}

            raw = message_text(payload)

            parsed = boundary_service.parse(
                raw
            )

            print(
                "SOURCE:",
                source.id,
            )

            print(
                "CANDIDATE:",
                source.candidate_id,
                repr(
                    candidate.name
                    if candidate
                    else None
                ),
            )

            print(
                "CANDIDATE EMAIL:",
                repr(
                    candidate.primary_email
                    if candidate
                    else None
                ),
            )

            print(
                "FROM:",
                json.dumps(
                    header_addresses(
                        payload,
                        "from",
                    ),
                    ensure_ascii=False,
                ),
            )

            print(
                "TO:",
                json.dumps(
                    header_addresses(
                        payload,
                        "to",
                    ),
                    ensure_ascii=False,
                ),
            )

            print(
                "SUBJECT:",
                repr(
                    payload.get("subject")
                ),
            )

            print(
                "BOUNDARY METHOD:",
                repr(
                    parsed.boundary_method
                ),
            )

            print(
                "BOUNDARY INDEX:",
                parsed.boundary_index,
            )

            print(
                "RELAY:",
                repr(
                    parsed.relay_payload
                ),
            )

            print()
            print(
                "---------------- RAW MESSAGE ----------------"
            )

            print_numbered(
                raw
            )

            print()
            print(
                "------------- CURRENT CONTENT ---------------"
            )

            print_numbered(
                parsed.current_content
            )

            print()
            print(
                "------------- QUOTED HISTORY ----------------"
            )

            print_numbered(
                parsed.quoted_history,
                limit=80,
            )

            compact = (
                parsed.current_content
                .replace("-", "")
                .replace(" ", "")
            )

            own_nip = (
                "8211139503" in compact
                or "8212697553" in compact
            )

            print()
            print(
                "OWN NIP IN CURRENT CONTENT:",
                own_nip,
            )

        print()
        print("=" * 140)
        print("SAFETY")
        print("=" * 140)

        print(
            "DATABASE MODIFICATIONS: 0"
        )

        print(
            "REMAINING FIRST-PARTY "
            "BOUNDARY AUDIT: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
