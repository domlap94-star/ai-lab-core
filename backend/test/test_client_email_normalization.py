from __future__ import annotations

from sqlalchemy.dialects import postgresql

from app.database.session import SessionLocal
from app.repositories.client_email_repository import ClientEmailRepository
from app.services.client_email_service import ClientEmailService


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    db = SessionLocal()
    try:
        service = ClientEmailService(db)

        require(
            service._direction({"direction": "sent"}) == "sent",
            "Explicit sent direction failed",
        )
        require(
            service._direction({"labelIds": ["SENT"]}) == "sent",
            "SENT label direction failed",
        )
        require(
            service._direction({"labelIds": ["INBOX"]}) == "received",
            "INBOX label direction failed",
        )
        require(
            service._direction({"labelIds": ["CATEGORY_UPDATES"]})
            == "unknown",
            "Unknown label was guessed",
        )

        addresses = service._addresses(
            {
                "value": [
                    {"name": "Jan Kowalski", "address": "JAN@example.com"},
                    {"name": "duplicate", "address": "jan@example.com"},
                ]
            }
        )
        require(
            addresses == [("Jan Kowalski", "jan@example.com")],
            "Structured address normalization failed",
        )
        require(
            service._addresses("Anna <anna@example.com>")
            == [("Anna", "anna@example.com")],
            "Raw Gmail header normalization failed",
        )
        require(
            service._addresses({"address": "IMPORT-TEST@Example.COM"})
            == [(None, "import-test@example.com")],
            "Direct structured address normalization failed",
        )
        require(
            service._addresses("missing-at.example.com") == [],
            "Malformed sender received authority",
        )

        current = service._body_text(
            {
                "text": (
                    "Bieżąca treść&nbsp;maila.\n\n"
                    "pt., 14 mar 2025 o 20:49 klient napisał(a):\n"
                    "> cytowana historia"
                )
            },
            None,
        )
        require(
            current == "Bieżąca treść maila.",
            "Current-message boundary or HTML entity normalization failed",
        )
        html_body = service._body_text(
            {
                "html": (
                    "<div>Dzień&nbsp;dobry</div><div>Druga linia</div>"
                    "<script>secret()</script>"
                )
            },
            None,
        )
        require(
            html_body == "Dzień dobry\n\nDruga linia",
            "Safe HTML-to-text normalization failed",
        )
        require(
            service._body_text({}, "Kontrolowany fallback")
            == "Kontrolowany fallback",
            "Extracted text fallback failed",
        )

        source_query = ClientEmailRepository(db)._deduplicated_sources(7)
        sql = str(
            source_query.select().compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        require(
            "row_number() OVER (PARTITION BY "
            "candidate_sources.import_source_id, "
            "candidate_sources.external_id" in sql,
            "Provenance-safe Gmail ID deduplication is missing",
        )
        require(
            "candidate_sources.source_type = 'gmail_message'" in sql,
            "Gmail-only source filter is missing",
        )
        require(
            "candidate_sources.deleted_at IS NULL" in sql
            and "client_candidates.deleted_at IS NULL" in sql,
            "Soft-delete filters are missing",
        )
        require(
            "client_candidates.matched_client_id = 7" in sql,
            "Provenance client filter is missing",
        )
        require(
            all(status in sql for status in ("accepted", "merged", "duplicate")),
            "Linked candidate status semantics are incomplete",
        )
        require(
            "lower(client_candidates.primary_email)" not in sql
            and "candidate_sources.raw_payload" in sql,
            "Ignored-state matching does not use the authoritative source sender",
        )

        print("CLIENT EMAIL NORMALIZATION: OK")
        print("direction=explicit/SENT/INBOX/unknown")
        print("body=current-boundary/html-entities/safe-html/extracted-fallback")
        print("query=gmail-only/provenance/soft-delete/dedupe")
        print("database_modifications=0")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
