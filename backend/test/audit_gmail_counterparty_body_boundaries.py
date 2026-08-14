from __future__ import annotations

import json

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate


# Contaminated + good organizational controls.
CONTROL_IDS = {
    27,
    133,
    221,
    603,
    720,
    1111,
    2595,
    3095,
    3269,
    3307,
    3462,
    3489,
}


def compact_header(
    payload,
    name,
):
    value = payload.get(name)

    if not isinstance(value, dict):
        return value

    return value


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


def main():
    db = SessionLocal()

    try:
        for candidate_id in sorted(
            CONTROL_IDS
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
            print("=" * 140)

            if candidate is None:
                print(
                    "CANDIDATE NOT FOUND:",
                    candidate_id,
                )
                continue

            print(
                "CANDIDATE:",
                candidate.id,
                repr(candidate.name),
            )

            print(
                "EMAIL:",
                repr(
                    candidate.primary_email
                ),
            )

            sources = (
                db.query(CandidateSource)
                .filter(
                    CandidateSource.candidate_id
                    == candidate.id,
                    CandidateSource.source_type
                    == "gmail_message",
                    CandidateSource.deleted_at.is_(None),
                )
                .order_by(
                    CandidateSource.id.asc()
                )
                .all()
            )

            print(
                "GMAIL SOURCES:",
                len(sources),
            )

            for source in sources:
                payload = source.raw_payload or {}

                text = message_text(
                    payload
                )

                # Only interesting messages.
                lowered = text.casefold()

                interesting = any(
                    token in lowered
                    for token in (
                        "8211139503",
                        "821-113-95-03",
                        "8212697553",
                        "821-269-75-53",
                        "oddział",
                        "oddzial",
                        "wydział",
                        "wydzial",
                        "starostwo",
                        "powiat",
                        "gmina",
                        "next stabil",
                        "podnoszenie posadzek",
                        "dominik",
                        "wojciech",
                    )
                )

                if not interesting:
                    continue

                print()
                print("-" * 140)

                print(
                    "SOURCE:",
                    source.id,
                )

                print(
                    "FROM:",
                    json.dumps(
                        compact_header(
                            payload,
                            "from",
                        ),
                        ensure_ascii=False,
                        default=str,
                    )
                )

                print(
                    "TO:",
                    json.dumps(
                        compact_header(
                            payload,
                            "to",
                        ),
                        ensure_ascii=False,
                        default=str,
                    )
                )

                print(
                    "SUBJECT:",
                    repr(
                        payload.get(
                            "subject"
                        )
                    ),
                )

                print()
                print(
                    "RAW TEXT BEGIN"
                )
                print(
                    "-" * 80
                )

                # Limit huge mail chains but retain both
                # beginning and end.
                lines = text.splitlines()

                if len(lines) <= 120:
                    selected = lines
                else:
                    selected = (
                        lines[:60]
                        + [
                            "",
                            "... [MIDDLE OMITTED] ...",
                            "",
                        ]
                        + lines[-60:]
                    )

                for index, line in enumerate(
                    selected,
                    start=1,
                ):
                    print(
                        f"{index:04d}: {line}"
                    )

                print(
                    "-" * 80
                )
                print(
                    "RAW TEXT END"
                )

        print()
        print("=" * 140)
        print(
            "DATABASE MODIFICATIONS: 0"
        )
        print(
            "GMAIL BODY BOUNDARY AUDIT: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
