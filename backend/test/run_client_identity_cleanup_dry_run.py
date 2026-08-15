from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from app.database.session import SessionLocal
from app.services.client_identity_cleanup_dry_run_service import (
    ClientIdentityCleanupDryRunService,
)


REPORT_DIR = Path(__file__).resolve().parent / "reports"
JSONL_PATH = REPORT_DIR / "client_identity_cleanup_dry_run.jsonl"
SUMMARY_PATH = REPORT_DIR / "client_identity_cleanup_summary.json"
TEXT_PATH = REPORT_DIR / "client_identity_cleanup_summary.txt"


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text("SET TRANSACTION READ ONLY"))
        read_only = db.execute(text("SHOW transaction_read_only")).scalar_one()
        if read_only != "on":
            raise RuntimeError("Dry-run transaction is not read-only")
        proposals, summary = ClientIdentityCleanupDryRunService(db).run()
        _validate(proposals, summary)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        JSONL_PATH.write_text(
            "".join(
                json.dumps(proposal.to_dict(), ensure_ascii=False) + "\n"
                for proposal in proposals
            ),
            encoding="utf-8",
        )
        SUMMARY_PATH.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        lines = ["CLIENT IDENTITY CLEANUP DRY-RUN", ""]
        for section, values in summary.items():
            lines.append(section.upper())
            if isinstance(values, dict):
                lines.extend(f"{key}: {value}" for key, value in values.items())
            else:
                lines.append(str(values))
            lines.append("")
        TEXT_PATH.write_text("\n".join(lines), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"records: {len(proposals)}")
        print("production database modifications: 0")
    finally:
        db.rollback()
        db.close()


def _validate(proposals, summary) -> None:
    if len({proposal.client_id for proposal in proposals}) != len(proposals):
        raise RuntimeError("Dry-run contains duplicate client records")
    if summary["suspicious"]["unique_total"] != len(proposals):
        raise RuntimeError("Summary and JSONL client counts disagree")
    if sum(summary["actions"].values()) != len(proposals):
        raise RuntimeError("Every suspicious client must have exactly one action")

    forbidden_methods = {
        "candidate_name_entity",
        "candidate_name_combined_entity_contact",
        "base_fallback",
    }
    for proposal in proposals:
        if any(item.method in forbidden_methods for item in proposal.evidence):
            raise RuntimeError("Self-evidence leaked into cleanup report")
        if proposal.action == "SAFE_RENAME_CANDIDATE":
            if not proposal.proposed_name or proposal.duplicate_risk != "NONE":
                raise RuntimeError("Unsafe proposal classified as SAFE")
        serialized = proposal.to_dict()
        if "raw_payload" in json.dumps(serialized):
            raise RuntimeError("raw_payload leaked into cleanup report")


if __name__ == "__main__":
    main()
