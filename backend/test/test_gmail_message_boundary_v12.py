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

OLD_FLATTENED_CONTROLS = {
    6496,
    6638,
    6651,
    6663,
    6776,
    6994,
}

NEW_W_DNIU_CONTROLS = {
    3007,
    3617,
    3956,
    4310,
}

NEW_OUTLOOK_CONTROLS = {
    3329,
    3622,
    5759,
    6447,
}

UNSTRUCTURED_INLINE_CONTROL = 6582

ALL_CONTROLS = (
    TRUE_RELAY_CONTROLS
    | QUOTED_RELAY_CONTROLS
    | FALSE_RELAY_CONTROLS
    | OLD_FLATTENED_CONTROLS
    | NEW_W_DNIU_CONTROLS
    | NEW_OUTLOOK_CONTROLS
    | {
        UNSTRUCTURED_INLINE_CONTROL
    }
)

OWN_NIPS = (
    "8211139503",
    "8212697553",
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


def compact(
    value,
):
    return (
        value
        .replace("-", "")
        .replace(" ", "")
    )


def has_own_nip(
    value,
):
    normalized = compact(
        value
    )

    return any(
        nip in normalized
        for nip in OWN_NIPS
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

        controls = {}
        counters = Counter()

        relay_rows = []

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
                    )
                )

            if source.id in ALL_CONTROLS:
                controls[
                    source.id
                ] = (
                    source.candidate_id,
                    parsed,
                )

        print()
        print("=" * 120)
        print(
            "GMAIL MESSAGE BOUNDARY 1.2 SUMMARY"
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
        print(
            "relay_source_count:",
            len(relay_rows),
        )

        relay_candidate_counts = Counter(
            candidate_id
            for candidate_id, _
            in relay_rows
        )

        print(
            "relay_candidate_count:",
            len(relay_candidate_counts),
        )

        for (
            candidate_id,
            count,
        ) in relay_candidate_counts.most_common():
            print(
                candidate_id,
                ":",
                count,
            )

        print()
        print("=" * 120)
        print("CONTROL RESULTS")
        print("=" * 120)

        for source_id in sorted(
            ALL_CONTROLS
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
                "own_nip_current:",
                has_own_nip(
                    parsed.current_content
                ),
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
                    parsed.quoted_history[:350]
                ),
            )

        # ====================================================
        # EXISTING 1.1 REGRESSIONS
        # ====================================================

        if len(relay_rows) != 47:
            raise RuntimeError(
                "Relay regression: expected 47, "
                f"got {len(relay_rows)}"
            )

        if set(
            relay_candidate_counts
        ) != {
            3095,
            3344,
        }:
            raise RuntimeError(
                "Relay candidate regression: "
                f"{set(relay_candidate_counts)}"
            )

        if (
            relay_candidate_counts[
                3095
            ] != 31
            or relay_candidate_counts[
                3344
            ] != 16
        ):
            raise RuntimeError(
                "Relay distribution regression."
            )

        for source_id in (
            TRUE_RELAY_CONTROLS
        ):
            if (
                controls[source_id][1]
                .relay_payload
                is None
            ):
                raise RuntimeError(
                    f"Relay missing: {source_id}"
                )

        for source_id in (
            QUOTED_RELAY_CONTROLS
            | FALSE_RELAY_CONTROLS
        ):
            if (
                controls[source_id][1]
                .relay_payload
                is not None
            ):
                raise RuntimeError(
                    "False relay regression: "
                    f"{source_id}"
                )

        for source_id in (
            OLD_FLATTENED_CONTROLS
        ):
            parsed = controls[
                source_id
            ][1]

            if has_own_nip(
                parsed.current_content
            ):
                raise RuntimeError(
                    "Old flattened boundary "
                    "regression: "
                    f"{source_id}"
                )

        # ====================================================
        # NEW 1.2 STRUCTURAL BOUNDARIES
        # ====================================================

        for source_id in (
            NEW_W_DNIU_CONTROLS
        ):
            parsed = controls[
                source_id
            ][1]

            if (
                parsed.boundary_method
                != "polish_w_dniu_reply"
            ):
                raise RuntimeError(
                    "Expected polish_w_dniu_reply "
                    f"for source {source_id}, got "
                    f"{parsed.boundary_method!r}"
                )

            if has_own_nip(
                parsed.current_content
            ):
                raise RuntimeError(
                    "Own NIP still present after "
                    "W dniu boundary for source "
                    f"{source_id}"
                )

        for source_id in (
            NEW_OUTLOOK_CONTROLS
        ):
            parsed = controls[
                source_id
            ][1]

            if parsed.boundary_method not in {
                "outlook_separator_header",
                "outlook_header",
            }:
                raise RuntimeError(
                    "Expected Outlook boundary "
                    f"for source {source_id}, got "
                    f"{parsed.boundary_method!r}"
                )

            if has_own_nip(
                parsed.current_content
            ):
                raise RuntimeError(
                    "Own NIP still present after "
                    "Outlook boundary for source "
                    f"{source_id}"
                )

        # ====================================================
        # INTENTIONALLY UNSOLVED CASE
        # ====================================================

        inline = controls[
            UNSTRUCTURED_INLINE_CONTROL
        ][1]

        if (
            inline.boundary_method
            is not None
        ):
            raise RuntimeError(
                "Source 6582 unexpectedly acquired "
                "a transport boundary. This case "
                "must remain delegated to the "
                "first-party content layer."
            )

        if not has_own_nip(
            inline.current_content
        ):
            raise RuntimeError(
                "Source 6582 no longer reproduces "
                "the known inline first-party leak."
            )

        print()
        print("=" * 120)
        print("VALIDATION")
        print("=" * 120)

        print(
            "existing relay regression: OK"
        )

        print(
            "existing flattened boundaries: OK"
        )

        print(
            "W dniu ISO boundaries: OK"
        )

        print(
            "Outlook header boundaries: OK"
        )

        print(
            "8/9 remaining structural leaks removed: OK"
        )

        print(
            "source 6582 delegated intentionally: OK"
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
            "GMAIL MESSAGE BOUNDARY 1.2: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
