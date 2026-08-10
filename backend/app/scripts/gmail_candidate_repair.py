from __future__ import annotations

import re
from collections import Counter

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.models.document import Document


OWN_EMAILS = {
    "podnoszenieposadzek@gmail.com",
    "kontakt@podnoszenieposadzek.pl",
    "domlap94@gmail.com",
    "lapa35@gmail.com",
}

EMAIL_ALIASES = {
    "zbyszek_jurkiewicz@02.pl": "zbyszek_jurkiewicz@o2.pl",
}

IGNORED_DOMAINS = {
    "google.com",
    "accounts.google.com",
    "mail.google.com",
    "notifications.google.com",
    "youtube.com",
    "youtube-nocookie.com",
}

IGNORED_EMAILS = {
    "no-reply@accounts.google.com",
    "no-reply@google.com",
    "noreply@google.com",
    "docs-noreply@google.com",
    "drive-shares-dm-noreply@google.com",
    "calendar-notification@google.com",
}

AUTOMATIC_PREFIXES = (
    "no-reply@",
    "noreply@",
    "do-not-reply@",
    "donotreply@",
    "mailer-daemon@",
    "postmaster@",
)

EMAIL_RE = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
    re.IGNORECASE,
)

FORWARDED_SENDER_RE = re.compile(
    r"(?im)^\s*(?:Od|From)\s*:\s*(.+)$"
)

FORWARDED_TO_RE = re.compile(
    r"(?im)^\s*(?:Do|To)\s*:\s*(.+)$"
)


def normalize_email(value: object) -> str | None:
    if value is None:
        return None

    match = EMAIL_RE.search(str(value))

    if not match:
        return None

    email = match.group(0).strip().lower()

    return EMAIL_ALIASES.get(
        email,
        email,
    )


def extract_all_emails(
    value: object,
) -> list[str]:
    if value is None:
        return []

    result = []

    for match in EMAIL_RE.findall(
        str(value)
    ):
        email = normalize_email(match)

        if email:
            result.append(email)

    return list(dict.fromkeys(result))


def get_domain(
    email: str | None,
) -> str | None:
    if not email or "@" not in email:
        return None

    return email.rsplit("@", 1)[1].lower()


def is_ignored(
    email: str | None,
) -> bool:
    if not email:
        return True

    normalized = normalize_email(email)

    if not normalized:
        return True

    if normalized in OWN_EMAILS:
        return True

    if normalized in IGNORED_EMAILS:
        return True

    domain = get_domain(normalized)

    if domain and domain in IGNORED_DOMAINS:
        return True

    return any(
        normalized.startswith(prefix)
        for prefix in AUTOMATIC_PREFIXES
    )


def extract_addresses(
    value: object,
) -> list[str]:
    if not value:
        return []

    result: list[str] = []

    if isinstance(value, dict):
        entries = value.get("value")

        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue

                email = normalize_email(
                    entry.get("address")
                )

                if email:
                    result.append(email)

            return list(dict.fromkeys(result))

        for key in (
            "address",
            "text",
        ):
            email = normalize_email(
                value.get(key)
            )

            if email:
                result.append(email)

        return list(dict.fromkeys(result))

    if isinstance(value, list):
        for entry in value:
            result.extend(
                extract_addresses(entry)
            )

        return list(dict.fromkeys(result))

    email = normalize_email(value)

    if email:
        result.append(email)

    return list(dict.fromkeys(result))


def has_sent_label(
    payload: dict,
) -> bool:
    labels = (
        payload.get("labelIds")
        or payload.get("labels")
        or []
    )

    if not isinstance(labels, list):
        return False

    for label in labels:
        if isinstance(label, str):
            value = label

        elif isinstance(label, dict):
            value = (
                label.get("id")
                or label.get("name")
                or ""
            )

        else:
            value = ""

        if str(value).upper() == "SENT":
            return True

    return False


def external_only(
    values: list[str],
) -> list[str]:
    return list(
        dict.fromkeys(
            email
            for email in values
            if not is_ignored(email)
        )
    )


def determine_envelope_contacts(
    payload: dict,
) -> list[str]:
    from_addresses = extract_addresses(
        payload.get("from")
        or payload.get("From")
    )

    to_addresses = extract_addresses(
        payload.get("to")
        or payload.get("To")
    )

    sent = has_sent_label(payload)

    counterpart = (
        to_addresses
        if sent
        else from_addresses
    )

    return external_only(counterpart)


def determine_forwarded_contacts(
    payload: dict,
) -> list[str]:
    text = (
        payload.get("text")
        or payload.get("textPlain")
        or payload.get("snippet")
        or ""
    )

    if not text:
        return []

    text = str(text)[:12000]

    sender_lines = (
        FORWARDED_SENDER_RE.findall(text)
    )

    to_lines = (
        FORWARDED_TO_RE.findall(text)
    )

    for line in sender_lines:
        emails = extract_all_emails(line)

        if not emails:
            continue

        external_senders = external_only(
            emails
        )

        if external_senders:
            return external_senders

        if any(
            email in OWN_EMAILS
            for email in emails
        ):
            for to_line in to_lines:
                external_recipients = (
                    external_only(
                        extract_all_emails(
                            to_line
                        )
                    )
                )

                if external_recipients:
                    return external_recipients

    return []


def determine_external_contacts(
    payload: dict,
) -> tuple[list[str], str]:
    envelope_contacts = (
        determine_envelope_contacts(
            payload
        )
    )

    if envelope_contacts:
        return (
            envelope_contacts,
            "envelope",
        )

    forwarded_contacts = (
        determine_forwarded_contacts(
            payload
        )
    )

    if forwarded_contacts:
        return (
            forwarded_contacts,
            "forwarded_headers",
        )

    return (
        [],
        "none",
    )


def create_candidate_for_email(
    db,
    email: str,
) -> ClientCandidate:
    candidate = ClientCandidate(
        client_type="person",
        name=email,
        primary_email=email,
        primary_phone=None,
        country_code="PL",
        notes=None,
        status="pending",
        confidence=0.75,
        matched_client_id=None,
        source_summary=(
            "gmail_repair | "
            f"{email}"
        ),
        raw_payload={
            "created_by": "gmail_candidate_repair",
            "primary_email": email,
        },
    )

    db.add(candidate)
    db.flush()

    return candidate


def main() -> None:
    db = SessionLocal()

    try:
        sources = (
            db.query(CandidateSource)
            .filter(
                CandidateSource.deleted_at.is_(None),
                CandidateSource.source_type
                == "gmail_message",
            )
            .order_by(
                CandidateSource.id.asc()
            )
            .all()
        )

        candidates = (
            db.query(ClientCandidate)
            .filter(
                ClientCandidate.deleted_at.is_(None)
            )
            .all()
        )

        candidate_by_id = {
            candidate.id: candidate
            for candidate in candidates
        }

        candidate_by_email: dict[
            str,
            ClientCandidate,
        ] = {}

        for candidate in candidates:
            email = normalize_email(
                candidate.primary_email
            )

            if (
                email
                and email not in candidate_by_email
            ):
                candidate_by_email[email] = (
                    candidate
                )

        counters = Counter()

        for source in sources:
            payload = (
                source.raw_payload
                or {}
            )

            current_candidate = (
                candidate_by_id.get(
                    source.candidate_id
                )
            )

            current_email = normalize_email(
                current_candidate.primary_email
                if current_candidate
                else None
            )

            external_contacts, method = (
                determine_external_contacts(
                    payload
                )
            )

            if len(external_contacts) == 0:
                counters[
                    "SKIP_NO_COUNTERPART"
                ] += 1
                continue

            if len(external_contacts) > 1:
                if (
                    current_email
                    and current_email
                    in external_contacts
                ):
                    counters[
                        "KEEP_MULTIPLE"
                    ] += 1
                else:
                    counters[
                        "SKIP_AMBIGUOUS"
                    ] += 1

                continue

            expected_email = (
                external_contacts[0]
            )

            if current_email == expected_email:
                counters["KEEP"] += 1
                continue

            target_candidate = (
                candidate_by_email.get(
                    expected_email
                )
            )

            if target_candidate is None:
                target_candidate = (
                    create_candidate_for_email(
                        db,
                        expected_email,
                    )
                )

                candidate_by_email[
                    expected_email
                ] = target_candidate

                candidate_by_id[
                    target_candidate.id
                ] = target_candidate

                counters[
                    "CREATED_CANDIDATE"
                ] += 1

            old_candidate_id = (
                source.candidate_id
            )

            source.candidate_id = (
                target_candidate.id
            )

            db.add(source)

            documents = (
                db.query(Document)
                .filter(
                    Document.source_type
                    == "gmail_attachment",
                    Document.gmail_message_id
                    == source.external_id,
                )
                .all()
            )

            moved_documents = 0

            for document in documents:
                if (
                    document.candidate_id
                    == target_candidate.id
                ):
                    continue

                document.candidate_id = (
                    target_candidate.id
                )

                document.match_status = (
                    "matched"
                )

                document.match_confidence = (
                    1.0
                )

                document.match_method = (
                    "gmail_message_repair"
                )

                db.add(document)

                moved_documents += 1

            counters["MOVED_SOURCE"] += 1
            counters[
                "MOVED_DOCUMENTS"
            ] += moved_documents

            print(
                "MOVE "
                f"source={source.id} "
                f"message={source.external_id} "
                f"from_candidate={old_candidate_id} "
                f"to_candidate={target_candidate.id} "
                f"email={expected_email} "
                f"method={method} "
                f"documents={moved_documents}"
            )

        db.commit()

        print()
        print(
            "===== GMAIL REPAIR COMPLETE ====="
        )

        for key in (
            "KEEP",
            "KEEP_MULTIPLE",
            "MOVED_SOURCE",
            "MOVED_DOCUMENTS",
            "CREATED_CANDIDATE",
            "SKIP_AMBIGUOUS",
            "SKIP_NO_COUNTERPART",
        ):
            print(
                f"{key:24} "
                f"{counters[key]}"
            )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()