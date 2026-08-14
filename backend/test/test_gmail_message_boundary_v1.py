from __future__ import annotations

from collections import Counter

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.services.gmail_message_boundary_service import (
    GmailMessageBoundaryService,
)


CONTROL_SOURCE_IDS = {
    # Bojarowicz - flattened quoted history with our NIP.
    6496,
    6638,
    6651,
    6663,
    6776,
    6994,

    # Relay controls.
    4836,
    5687,
    6036,

    # Real customer replies containing relay only in history.
    5311,
    5735,
}


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
        service = (
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

        first_party_nip_leaks = []

        relay_sources = []

        controls = {}

        for source in sources:
            payload = (
                source.raw_payload
                or {}
            )

            raw = message_text(
                payload
            )

            parsed = service.parse(
                raw
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

                relay_sources.append(
                    (
                        source.candidate_id,
                        source.id,
                        parsed.relay_payload,
                    )
                )

            compact_current = (
                parsed.current_content
                .replace("-", "")
                .replace(" ", "")
            )

            if (
                "8212697553"
                in compact_current
                or "8211139503"
                in compact_current
            ):
                first_party_nip_leaks.append(
                    (
                        source.candidate_id,
                        source.id,
                        parsed.boundary_method,
                        parsed.current_content[:700],
                    )
                )

            if source.id in CONTROL_SOURCE_IDS:
                controls[source.id] = (
                    source.candidate_id,
                    parsed,
                )

        print()
        print("=" * 120)
        print("GMAIL MESSAGE BOUNDARY 1.0 SUMMARY")
        print("=" * 120)

        print(
            "gmail_sources:",
            len(sources),
        )

        for key in sorted(counters):
            print(
                key,
                ":",
                counters[key],
            )

        print()
        print("=" * 120)
        print("CONTROL SOURCES")
        print("=" * 120)

        for source_id in sorted(
            CONTROL_SOURCE_IDS
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
                "boundary_method:",
                repr(
                    parsed.boundary_method
                ),
            )

            print(
                "boundary_index:",
                parsed.boundary_index,
            )

            print(
                "relay:",
                parsed.relay_payload,
            )

            print(
                "CURRENT:",
                repr(
                    parsed.current_content[:1000]
                ),
            )

            print(
                "QUOTED:",
                repr(
                    parsed.quoted_history[:500]
                ),
            )

        print()
        print("=" * 120)
        print("RELAY CURRENT-CONTENT RESULTS")
        print("=" * 120)

        print(
            "relay_source_count:",
            len(relay_sources),
        )

        for (
            candidate_id,
            source_id,
            relay,
        ) in relay_sources[:100]:
            print(
                candidate_id,
                "| source:",
                source_id,
                "| email:",
                repr(relay.email),
                "| name:",
                repr(relay.name),
                "| message:",
                repr(
                    (
                        relay.message
                        or ""
                    )[:250]
                ),
            )

        print()
        print("=" * 120)
        print("FIRST-PARTY NIP IN CURRENT CONTENT")
        print("=" * 120)

        print(
            "nip_current_content_count:",
            len(first_party_nip_leaks),
        )

        for (
            candidate_id,
            source_id,
            method,
            preview,
        ) in first_party_nip_leaks[:100]:
            print(
                candidate_id,
                "| source:",
                source_id,
                "| boundary:",
                repr(method),
                "|",
                repr(preview),
            )

        # ----------------------------------------------------
        # Hard control expectations.
        # ----------------------------------------------------

        expected_relay = {
            4836,
            5687,
            6036,
        }

        for source_id in expected_relay:
            parsed = controls[
                source_id
            ][1]

            if parsed.relay_payload is None:
                raise RuntimeError(
                    "Expected relay payload missing "
                    f"for source {source_id}"
                )

        # Relay inside quoted history must NOT make current
        # customer reply a relay.
        for source_id in (
            5311,
            5735,
        ):
            parsed = controls[
                source_id
            ][1]

            if parsed.relay_payload is not None:
                raise RuntimeError(
                    "Quoted relay leaked into current "
                    f"content for source {source_id}"
                )

        # Bojarowicz flattened customer messages must not
        # retain our NIP in current-author content.
        for source_id in (
            6496,
            6638,
            6651,
            6663,
            6776,
            6994,
        ):
            parsed = controls[
                source_id
            ][1]

            compact = (
                parsed.current_content
                .replace("-", "")
                .replace(" ", "")
            )

            if (
                "8212697553" in compact
                or "8211139503" in compact
            ):
                raise RuntimeError(
                    "Quoted first-party NIP leaked "
                    f"for source {source_id}"
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

        print(
            "GMAIL MESSAGE BOUNDARY 1.0: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
