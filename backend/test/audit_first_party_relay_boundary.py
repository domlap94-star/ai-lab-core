from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.models.import_source import ImportSource


CONTROL_IDS = (
    2595,
    3095,
)

RELAY_FIELD_RE = re.compile(
    r"(?:^|\n|\s{2,})"
    r"(?:Od|Z|From)\s*:\s*\{?[^{}\n]{2,200}\}?"
    r".{0,500}?"
    r"Nazwa\s*:\s*\{?[^{}\n]{1,200}\}?"
    r".{0,500}?"
    r"Wiadomo(?:ść|sc|┼Ť─ç)\s*:",
    re.IGNORECASE | re.DOTALL,
)

POLISH_REPLY_RE = re.compile(
    r"(?:"
    r"\bDnia\s+\d{1,2}\s+"
    r"|"
    r"\b(?:pon|wt|śr|sr|czw|pt|sob|niedz)\.?,?\s+"
    r"\d{1,2}\s+"
    r")"
    r".{0,400}?"
    r"napisa.{0,12}?:",
    re.IGNORECASE | re.DOTALL,
)

GENERIC_REPLY_RE = re.compile(
    r".{0,250}?"
    r"(?:wrote|napisa.{0,12})\s*:",
    re.IGNORECASE | re.DOTALL,
)


def clean(value) -> str:
    if value is None:
        return ""

    return str(value).strip()


def normalize_email(value) -> str:
    value = clean(value).casefold()

    if (
        "@" not in value
        or " " in value
    ):
        return ""

    return value


def header_addresses(
    payload: dict,
    field_name: str,
) -> list[str]:
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

        address = normalize_email(
            item.get("address")
        )

        if address:
            result.append(address)

    return result


def message_text(
    payload: dict,
) -> str:
    for key in (
        "text",
        "textPlain",
        "snippet",
    ):
        value = payload.get(key)

        if value:
            return str(value)

    return ""


def main() -> None:
    db = SessionLocal()

    try:
        print()
        print("=" * 140)
        print("IMPORT SOURCES")
        print("=" * 140)

        import_sources = (
            db.query(ImportSource)
            .filter(
                ImportSource.deleted_at.is_(None)
            )
            .order_by(
                ImportSource.id.asc()
            )
            .all()
        )

        known_import_accounts = set()

        for source in import_sources:
            external_account_id = clean(
                source.external_account_id
            )

            normalized_account = normalize_email(
                external_account_id
            )

            if normalized_account:
                known_import_accounts.add(
                    normalized_account
                )

            print()
            print(
                "id:",
                source.id,
            )
            print(
                "source_type:",
                repr(source.source_type),
            )
            print(
                "display_name:",
                repr(source.display_name),
            )
            print(
                "external_account_id:",
                repr(source.external_account_id),
            )
            print(
                "status:",
                repr(source.status),
            )
            print(
                "is_enabled:",
                repr(source.is_enabled),
            )

            configuration = (
                source.configuration
            )

            if configuration is not None:
                print(
                    "configuration:",
                    json.dumps(
                        configuration,
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    ),
                )

        print()
        print(
            "KNOWN IMPORT ACCOUNT EMAILS:",
            sorted(known_import_accounts),
        )

        print()
        print("=" * 140)
        print("GLOBAL GMAIL DIRECTION / RELAY AUDIT")
        print("=" * 140)

        gmail_sources = (
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

        sender_candidate_counts = Counter()
        receiver_candidate_counts = Counter()

        relay_candidates = Counter()
        flattened_reply_candidates = Counter()

        relay_examples = []
        flattened_examples = []

        for source in gmail_sources:
            payload = source.raw_payload or {}

            text = message_text(
                payload
            )

            from_addresses = (
                header_addresses(
                    payload,
                    "from",
                )
            )

            to_addresses = (
                header_addresses(
                    payload,
                    "to",
                )
            )

            candidate = (
                db.query(ClientCandidate)
                .filter(
                    ClientCandidate.id
                    == source.candidate_id
                )
                .first()
            )

            candidate_email = (
                normalize_email(
                    candidate.primary_email
                )
                if candidate is not None
                else ""
            )

            if (
                candidate_email
                and candidate_email
                in from_addresses
            ):
                counters[
                    "candidate_is_sender"
                ] += 1

                sender_candidate_counts[
                    source.candidate_id
                ] += 1

            if (
                candidate_email
                and candidate_email
                in to_addresses
            ):
                counters[
                    "candidate_is_receiver"
                ] += 1

                receiver_candidate_counts[
                    source.candidate_id
                ] += 1

            if any(
                address in known_import_accounts
                for address in from_addresses
            ):
                counters[
                    "from_import_account"
                ] += 1

            if any(
                address in known_import_accounts
                for address in to_addresses
            ):
                counters[
                    "to_import_account"
                ] += 1

            relay_match = (
                RELAY_FIELD_RE.search(
                    text
                )
            )

            if relay_match:
                counters[
                    "relay_grammar_messages"
                ] += 1

                relay_candidates[
                    source.candidate_id
                ] += 1

                if len(relay_examples) < 80:
                    relay_examples.append(
                        (
                            source.candidate_id,
                            source.id,
                            from_addresses,
                            to_addresses,
                            text[:700],
                        )
                    )

            flattened_match = (
                POLISH_REPLY_RE.search(
                    text
                )
            )

            if flattened_match:
                counters[
                    "flattened_polish_reply_messages"
                ] += 1

                flattened_reply_candidates[
                    source.candidate_id
                ] += 1

                if len(flattened_examples) < 80:
                    start = max(
                        0,
                        flattened_match.start()
                        - 250,
                    )

                    end = min(
                        len(text),
                        flattened_match.end()
                        + 350,
                    )

                    flattened_examples.append(
                        (
                            source.candidate_id,
                            source.id,
                            text[start:end],
                        )
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
            "gmail_sources:",
            len(gmail_sources),
        )

        print()
        print(
            "relay_candidate_count:",
            len(relay_candidates),
        )

        print(
            "flattened_reply_candidate_count:",
            len(flattened_reply_candidates),
        )

        print()
        print("=" * 140)
        print("TOP RELAY-LIKE CANDIDATES")
        print("=" * 140)

        for candidate_id, count in (
            relay_candidates.most_common(50)
        ):
            candidate = (
                db.query(ClientCandidate)
                .filter(
                    ClientCandidate.id
                    == candidate_id
                )
                .first()
            )

            print(
                candidate_id,
                "|",
                repr(
                    candidate.name
                    if candidate
                    else None
                ),
                "| email:",
                repr(
                    candidate.primary_email
                    if candidate
                    else None
                ),
                "| relay_messages:",
                count,
                "| candidate_sender:",
                sender_candidate_counts[
                    candidate_id
                ],
                "| candidate_receiver:",
                receiver_candidate_counts[
                    candidate_id
                ],
            )

        print()
        print("=" * 140)
        print("CONTROL CANDIDATES")
        print("=" * 140)

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
                "client_type:",
                repr(candidate.client_type),
            )

            print(
                "sender_messages:",
                sender_candidate_counts[
                    candidate_id
                ],
            )

            print(
                "receiver_messages:",
                receiver_candidate_counts[
                    candidate_id
                ],
            )

            print(
                "relay_grammar_messages:",
                relay_candidates[
                    candidate_id
                ],
            )

            print(
                "flattened_reply_messages:",
                flattened_reply_candidates[
                    candidate_id
                ],
            )

            sources = (
                db.query(CandidateSource)
                .filter(
                    CandidateSource.candidate_id
                    == candidate_id,
                    CandidateSource.source_type
                    == "gmail_message",
                    CandidateSource.deleted_at.is_(None),
                )
                .order_by(
                    CandidateSource.id.asc()
                )
                .all()
            )

            for source in sources:
                payload = (
                    source.raw_payload
                    or {}
                )

                from_addresses = (
                    header_addresses(
                        payload,
                        "from",
                    )
                )

                to_addresses = (
                    header_addresses(
                        payload,
                        "to",
                    )
                )

                text = message_text(
                    payload
                )

                relay = bool(
                    RELAY_FIELD_RE.search(
                        text
                    )
                )

                flattened = bool(
                    POLISH_REPLY_RE.search(
                        text
                    )
                )

                print(
                    "source",
                    source.id,
                    "| from:",
                    from_addresses,
                    "| to:",
                    to_addresses,
                    "| relay:",
                    relay,
                    "| flattened_reply:",
                    flattened,
                    "| subject:",
                    repr(
                        payload.get(
                            "subject"
                        )
                    ),
                )

        print()
        print("=" * 140)
        print("RELAY EXAMPLES")
        print("=" * 140)

        for (
            candidate_id,
            source_id,
            from_addresses,
            to_addresses,
            preview,
        ) in relay_examples:
            print()
            print(
                "candidate:",
                candidate_id,
                "| source:",
                source_id,
            )
            print(
                "from:",
                from_addresses,
            )
            print(
                "to:",
                to_addresses,
            )
            print(
                repr(preview),
            )

        print()
        print("=" * 140)
        print("FLATTENED REPLY EXAMPLES")
        print("=" * 140)

        for (
            candidate_id,
            source_id,
            excerpt,
        ) in flattened_examples:
            print()
            print(
                "candidate:",
                candidate_id,
                "| source:",
                source_id,
            )
            print(
                repr(excerpt),
            )

        print()
        print("=" * 140)
        print("SAFETY")
        print("=" * 140)
        print(
            "DATABASE MODIFICATIONS: 0"
        )
        print(
            "FIRST-PARTY / RELAY AUDIT: OK"
        )

    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
