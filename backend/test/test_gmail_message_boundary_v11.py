from __future__ import annotations

from collections import Counter

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.services.gmail_message_boundary_service import (
    GmailMessageBoundaryService,
)


TRUE_RELAY_CONTROLS = {
    4836,
    5687,
    6036,
}

QUOTED_RELAY_CONTROLS = {
    5311,
    5735,
}

FALSE_RELAY_CONTROLS = {
    2726,
    3746,
}

BOJAROWICZ_CONTROLS = {
    6496,
    6638,
    6651,
    6663,
    6776,
    6994,
}

CONTROL_IDS = (
    TRUE_RELAY_CONTROLS
    | QUOTED_RELAY_CONTROLS
    | FALSE_RELAY_CONTROLS
    | BOJAROWICZ_CONTROLS
)


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


def compact_nip_text(
    text: str,
) -> str:
    return (
        text
        .replace("-", "")
        .replace(" ", "")
    )


def main():
    db = SessionLocal()

    try:
        parser = (
            GmailMessageBoundaryService()
        )

        sources = (
            db.query(CandidateSource)
            .filter(
                CandidateSource.source_type
                == "gmail_message",
                CandidateSource.deleted_at.is_(None),
            )
            .order_by(
                CandidateSource.id.asc()
            )
            .all()
        )

        counters = Counter()

        relay_rows = []

        controls = {}

        for source in sources:
            payload = (
                source.raw_payload
                or {}
            )

            parsed = parser.parse(
                message_text(
                    payload
                )
            )

            if parsed.boundary_method:
                counters[
                    "boundary_detected"
                ] += 1

                counters[
                    "boundary_"
                    + parsed.boundary_method
                ] += 1

            else:
                counters[
                    "no_boundary"
                ] += 1

            if parsed.relay_payload:
                counters[
                    "relay_current_content"
                ] += 1

                relay_rows.append(
                    (
                        source.candidate_id,
                        source.id,
                        parsed.relay_payload,
                    )
                )

            if source.id in CONTROL_IDS:
                controls[
                    source.id
                ] = (
                    source.candidate_id,
                    parsed,
                )

        print()
        print("=" * 120)
        print(
            "GMAIL MESSAGE BOUNDARY 1.1 SUMMARY"
        )
        print("=" * 120)

        print(
            "gmail_sources:",
            len(sources),
        )

        for key in sorted(
            counters
        ):
            print(
                key,
                ":",
                counters[key],
            )

        print()
        print("=" * 120)
        print("STRICT RELAY RESULTS")
        print("=" * 120)

        print(
            "relay_source_count:",
            len(relay_rows),
        )

        relay_candidate_counts = Counter(
            candidate_id
            for (
                candidate_id,
                _,
                _,
            ) in relay_rows
        )

        print(
            "relay_candidate_count:",
            len(
                relay_candidate_counts
            ),
        )

        for candidate_id, count in (
            relay_candidate_counts.most_common()
        ):
            print(
                candidate_id,
                ":",
                count,
            )

        print()
        print("=" * 120)
        print("CONTROL SOURCES")
        print("=" * 120)

        for source_id in sorted(
            CONTROL_IDS
        ):
            item = controls.get(
                source_id
            )

            print()
            print("-" * 120)

            if item is None:
                print(
                    source_id,
                    "| NOT FOUND"
                )
                continue

            candidate_id, parsed = item

            print(
                "source_id:",
                source_id,
            )

            print(
                "candidate_id:",
                candidate_id,
            )

            print(
                "boundary:",
                repr(
                    parsed.boundary_method
                ),
            )

            print(
                "relay:",
                parsed.relay_payload,
            )

            print(
                "current:",
                repr(
                    parsed.current_content[:700]
                ),
            )

            print(
                "quoted:",
                repr(
                    parsed.quoted_history[:300]
                ),
            )

        # ====================================================
        # HARD EXPECTATIONS
        # ====================================================

        if len(relay_rows) != 47:
            raise RuntimeError(
                "Expected exactly 47 strict relay "
                f"messages, got {len(relay_rows)}"
            )

        if set(
            relay_candidate_counts
        ) != {
            3095,
            3344,
        }:
            raise RuntimeError(
                "Strict relay candidates differ "
                "from expected {3095, 3344}: "
                f"{set(relay_candidate_counts)}"
            )

        if (
            relay_candidate_counts[
                3095
            ] != 31
        ):
            raise RuntimeError(
                "Candidate 3095 expected 31 "
                "relay messages."
            )

        if (
            relay_candidate_counts[
                3344
            ] != 16
        ):
            raise RuntimeError(
                "Candidate 3344 expected 16 "
                "relay messages."
            )

        for source_id in (
            TRUE_RELAY_CONTROLS
        ):
            parsed = controls[
                source_id
            ][1]

            if parsed.relay_payload is None:
                raise RuntimeError(
                    "Expected relay missing for "
                    f"source {source_id}"
                )

        for source_id in (
            QUOTED_RELAY_CONTROLS
            | FALSE_RELAY_CONTROLS
        ):
            parsed = controls[
                source_id
            ][1]

            if parsed.relay_payload is not None:
                raise RuntimeError(
                    "False relay detected for "
                    f"source {source_id}"
                )

        for source_id in (
            BOJAROWICZ_CONTROLS
        ):
            parsed = controls[
                source_id
            ][1]

            compact = compact_nip_text(
                parsed.current_content
            )

            if (
                "8212697553"
                in compact
                or "8211139503"
                in compact
            ):
                raise RuntimeError(
                    "Quoted own NIP leaked into "
                    "current content for source "
                    f"{source_id}"
                )

        print()
        print("=" * 120)
        print("VALIDATION")
        print("=" * 120)

        print(
            "strict relay count 47: OK"
        )
        print(
            "relay candidates {3095, 3344}: OK"
        )
        print(
            "3095 relay count 31: OK"
        )
        print(
            "3344 relay count 16: OK"
        )
        print(
            "quoted relay isolation: OK"
        )
        print(
            "false relay controls: OK"
        )
        print(
            "flattened reply boundary controls: OK"
        )

        print()
        print("=" * 120)
        print("SAFETY")
        print("=" * 120)

        print(
            "DATABASE MODIFICATIONS: 0"
        )

        print(
            "CRM PROJECTION MODIFICATIONS: 0"
        )

        print()
        print(
            "GMAIL MESSAGE BOUNDARY 1.1: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
