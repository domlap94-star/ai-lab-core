from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from app.database.session import SessionLocal
from app.services.client_notes_email_cleanup_dry_run_service import (
    ClientNotesEmailCleanupDryRunService,
)


REPORT_DIR = Path(__file__).resolve().parent / "reports"
DRY_RUN_PATH = REPORT_DIR / "client_notes_email_cleanup_dry_run.jsonl"
SUMMARY_PATH = REPORT_DIR / "client_notes_email_cleanup_summary.json"
REVIEW_PATH = REPORT_DIR / "client_notes_email_cleanup_review.json"
SUMMARY_TEXT_PATH = REPORT_DIR / "client_notes_email_cleanup_summary.txt"
SAFE_MANIFEST_PATH = REPORT_DIR / "client_notes_email_cleanup_safe_manifest.json"


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        db.execute(text("SET TRANSACTION READ ONLY"))
        proposals, summary = ClientNotesEmailCleanupDryRunService(db).run()
        DRY_RUN_PATH.write_text(
            "".join(
                json.dumps(item.report_record(), ensure_ascii=False) + "\n"
                for item in proposals
            ),
            encoding="utf-8",
        )
        _write_json(SUMMARY_PATH, summary)
        review = [
            {
                **item.report_record(),
                "review_reason": "source cross-check or block boundary is not conclusive",
            }
            for item in proposals
            if item.classification in {
                "REVIEW_REQUIRED",
                "BLOCKED_NO_SOURCE_HISTORY",
            }
        ]
        _write_json(REVIEW_PATH, {"records": review})
        safe = [
            {
                "client_id": item.client_id,
                "expected_before_sha256": item.before_sha256,
                "proposed_after_sha256": item.proposed_notes_sha256,
                "classification": item.classification,
            }
            for item in proposals
            if item.classification in {
                "SAFE_REMOVE_TRANSCRIPT_ONLY",
                "SAFE_CLEAR_NOTES",
            }
        ]
        _write_json(
            SAFE_MANIFEST_PATH,
            {
                "approval_scope": "CHUNK_6C_DRY_RUN_ONLY_NOT_APPROVED_FOR_APPLY",
                "approved_for_apply": False,
                "record_count": len(safe),
                "records": safe,
            },
        )
        SUMMARY_TEXT_PATH.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        db.rollback()
    finally:
        db.close()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"REPORT RECORDS: {len(proposals)}")
    print(f"SAFE MANIFEST RECORDS: {len(safe)}")
    print("production database modifications = 0")


if __name__ == "__main__":
    main()
