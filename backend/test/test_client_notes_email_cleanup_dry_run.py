from __future__ import annotations

from datetime import datetime, timezone

from app.services.client_notes_email_cleanup_dry_run_service import (
    ClientNotesEmailCleanupDryRunService,
    LegacyEmailNotesParser,
    SourceMessage,
    notes_sha256,
)


DATE = "2025-01-02T03:04:05.000Z"


def transcript(subject: str = "Oferta", body: str = "Treść") -> str:
    return "\n".join(
        (
            "Kierunek wiadomości: Odebrana",
            f"Temat wiadomości: {subject}",
            f"Data wiadomości: {DATE}",
            f"Treść wiadomości: {body}",
        )
    )


def source(subject: str = "Oferta", body: str = "Treść") -> SourceMessage:
    return SourceMessage(
        source_id=1,
        direction="received",
        message_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        subject=subject,
        body=body,
    )


def proposal(notes: str, messages: list[SourceMessage]):
    service = object.__new__(ClientNotesEmailCleanupDryRunService)
    service.email_normalizer = __import__(
        "app.services.client_email_service",
        fromlist=["ClientEmailService"],
    ).ClientEmailService.__new__(
        __import__(
            "app.services.client_email_service",
            fromlist=["ClientEmailService"],
        ).ClientEmailService
    )
    return service._proposal(
        client_id=10,
        notes=notes,
        parsed=LegacyEmailNotesParser.parse(notes),
        messages=messages,
    )


def main() -> None:
    only = proposal(transcript(), [source()])
    assert only.classification == "SAFE_CLEAR_NOTES"
    assert only.proposed_notes is None

    prefix = "Ważna ręczna notatka: zachować ąęł."
    with_prefix = proposal(prefix + "\n\n" + transcript(), [source()])
    assert with_prefix.classification == "SAFE_REMOVE_TRANSCRIPT_ONLY"
    assert with_prefix.proposed_notes == prefix

    suffix = "Ręczny dopisek po wiadomości."
    with_suffix = proposal(transcript() + "\n\n" + suffix, [source()])
    assert with_suffix.proposed_notes == suffix

    both = proposal(prefix + "\n\n" + transcript() + "\n\n" + suffix, [source()])
    assert both.proposed_notes == prefix + "\n\n" + suffix
    assert both.transcript_positions == ("between_manual_content",)

    crlf = prefix + "\r\n\r\n" + transcript().replace("\n", "\r\n")
    crlf_result = proposal(crlf, [source()])
    assert crlf_result.proposed_notes == prefix

    second = transcript("Drugi temat", "Druga treść")
    messages = [source(), source("Drugi temat", "Druga treść")]
    multiple = proposal(prefix + "\n\n" + transcript() + "\n\n" + second + "\n\n" + suffix, messages)
    assert multiple.removed_block_count == 2
    assert multiple.proposed_notes == prefix + "\n\n" + suffix

    malformed = transcript().replace("Data wiadomości:", "Data:")
    malformed_result = proposal(malformed, [source()])
    assert malformed_result.classification == "REVIEW_REQUIRED"
    assert malformed_result.proposed_notes == malformed

    single_marker = "Manualny temat wiadomości: omówić jutro."
    parsed_single = LegacyEmailNotesParser.parse(single_marker)
    assert parsed_single.blocks == ()
    assert parsed_single.proposed_notes == single_marker

    body_like_manual = prefix + "\n\n" + "Treść wiadomości z Gmaila, ale ręcznie zapisana."
    parsed_body = LegacyEmailNotesParser.parse(body_like_manual)
    assert parsed_body.blocks == ()
    assert parsed_body.proposed_notes == body_like_manual

    assert notes_sha256(transcript()) == notes_sha256(transcript())
    assert notes_sha256(None) != notes_sha256("")

    blocked = proposal(transcript(), [])
    assert blocked.classification == "BLOCKED_NO_SOURCE_HISTORY"
    assert blocked.proposed_notes == transcript()
    assert blocked.removed_block_count == 0

    no_match = proposal(transcript(), [source(subject="Inny temat")])
    assert no_match.classification == "REVIEW_REQUIRED"
    assert no_match.proposed_notes == transcript()

    ambiguous_sources = proposal(transcript(), [source(), source()])
    assert ambiguous_sources.classification == "REVIEW_REQUIRED"

    before = transcript()
    result = proposal(before, [source()])
    assert result.before_sha256 == notes_sha256(before)
    assert result.proposed_notes_sha256 == notes_sha256(None)
    assert result.before_length == len(before)
    assert result.removed_character_count == len(before)

    print("CLIENT NOTES EMAIL CLEANUP DRY-RUN TESTS: OK")
    print("production database modifications = 0")


if __name__ == "__main__":
    main()
