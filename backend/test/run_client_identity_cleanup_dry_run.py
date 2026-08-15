from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from app.database.session import SessionLocal
from app.services.client_identity_cleanup_dry_run_service import (
    ClientIdentityCleanupDryRunService,
)
from app.services.client_identity_name_quality_service import (
    ClientIdentityNameQualityService,
)


REPORT_DIR = Path(__file__).resolve().parent / "reports"
JSONL_PATH = REPORT_DIR / "client_identity_cleanup_dry_run.jsonl"
SUMMARY_PATH = REPORT_DIR / "client_identity_cleanup_summary.json"
TEXT_PATH = REPORT_DIR / "client_identity_cleanup_summary.txt"
HUMAN_REVIEW_PATH = REPORT_DIR / "client_identity_cleanup_human_review.json"


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(text("SET TRANSACTION READ ONLY"))
        read_only = db.execute(text("SHOW transaction_read_only")).scalar_one()
        if read_only != "on":
            raise RuntimeError("Dry-run transaction is not read-only")
        proposals, summary = ClientIdentityCleanupDryRunService(db).run()
        _validate(proposals, summary)
        summary["insufficient_sample"] = _insufficient_sample(proposals)
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
        HUMAN_REVIEW_PATH.write_text(
            json.dumps(
                {
                    "data_impact": "DRY-RUN ONLY — PRODUCTION WRITES 0",
                    "items": _human_review_items(proposals),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
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
            if (
                not proposal.proposed_name
                or proposal.duplicate_risk != "NONE"
                or not proposal.identity_support_evidence
                or proposal.confidence < 0.90
            ):
                raise RuntimeError("Unsafe proposal classified as SAFE")
            normalized = ClientIdentityNameQualityService.normalize_identity(
                proposal.proposed_name
            )
            if any(
                ClientIdentityNameQualityService.normalize_identity(
                    evidence.value
                )
                != normalized
                for evidence in proposal.identity_support_evidence
            ):
                raise RuntimeError("SAFE identity support targets another value")
        serialized = proposal.to_dict()
        if "raw_payload" in json.dumps(serialized):
            raise RuntimeError("raw_payload leaked into cleanup report")


def _human_review_items(proposals) -> list[dict]:
    actions = {
        "SAFE_RENAME_CANDIDATE",
        "REVIEW_REQUIRED",
        "POTENTIAL_DUPLICATE_OR_MERGE",
        "FIRST_PARTY_OR_RELAY_REVIEW",
    }
    result = []
    for proposal in proposals:
        if proposal.action not in actions:
            continue
        support_keys = {
            (
                item.candidate_id,
                item.source_id,
                item.method,
                item.value.casefold(),
            )
            for item in proposal.identity_support_evidence
        }
        other_evidence = [
            item
            for item in proposal.evidence
            if (
                item.candidate_id,
                item.source_id,
                item.method,
                item.value.casefold(),
            )
            not in support_keys
        ]
        result.append(
            {
                "client_id": proposal.client_id,
                "suspicion_types": proposal.suspicion_types,
                "current_name": proposal.current_name,
                "current_client_type": proposal.current_client_type,
                "primary_email": proposal.primary_email,
                "primary_phone": proposal.primary_phone,
                "proposed_name": proposal.proposed_name,
                "proposed_client_type": proposal.proposed_client_type,
                "identity_confidence": proposal.confidence,
                "action": proposal.action,
                "safety_reason": proposal.safety_reason,
                "duplicate_risk": proposal.duplicate_risk,
                "potential_duplicate_client_ids": (
                    proposal.potential_duplicate_client_ids
                ),
                "candidate_ids": proposal.candidate_ids,
                "conflicts": proposal.conflicts,
                "identity_support_evidence": [
                    {
                        "candidate_id": item.candidate_id,
                        "source_id": item.source_id,
                        "source_type": item.source_type,
                        "method": item.method,
                        "value": item.value,
                        "confidence": item.confidence,
                    }
                    for item in proposal.identity_support_evidence
                ],
                "other_evidence": [
                    {
                        "candidate_id": item.candidate_id,
                        "source_id": item.source_id,
                        "source_type": item.source_type,
                        "method": item.method,
                        "value": item.value,
                        "confidence": item.confidence,
                    }
                    for item in other_evidence
                ],
            }
        )
    return result


def _insufficient_sample(proposals) -> list[dict]:
    insufficient = [
        proposal
        for proposal in proposals
        if proposal.action == "INSUFFICIENT_EVIDENCE"
    ]
    selected = []
    selected_ids = set()

    def add(category: str, limit: int) -> None:
        for proposal in insufficient:
            if len([p for p in selected if category in p.suspicion_types]) >= limit:
                return
            if proposal.client_id in selected_ids or category not in proposal.suspicion_types:
                continue
            selected.append(proposal)
            selected_ids.add(proposal.client_id)

    add("EMAIL_AS_NAME", 5)
    add("PHONE_AS_NAME", 5)
    add("FILE_AS_NAME", 1)

    profiles = (
        lambda p: p.diagnostics["has_gmail_source"]
        and p.diagnostics["has_sheets_source"],
        lambda p: "quoted_history_excluded_by_boundary"
        in p.diagnostics["why_insufficient"],
        lambda p: p.diagnostics["has_gmail_source"]
        and not p.diagnostics["has_sheets_source"],
        lambda p: p.diagnostics["document_count"] > 0,
        lambda p: p.diagnostics["has_sheets_source"]
        and not p.diagnostics["has_gmail_source"]
        and p.diagnostics["document_count"] > 0,
    )
    for profile in profiles:
        match = next(
            (
                proposal
                for proposal in insufficient
                if proposal.client_id not in selected_ids and profile(proposal)
            ),
            None,
        )
        if match is not None:
            selected.append(match)
            selected_ids.add(match.client_id)

    for proposal in insufficient:
        if len(selected) >= 15:
            break
        if proposal.client_id in selected_ids:
            continue
        selected.append(proposal)
        selected_ids.add(proposal.client_id)

    return [
        {
            "client_id": proposal.client_id,
            "suspicion": proposal.suspicion_types,
            "current_name_masked": _mask_name(proposal.current_name),
            "candidate_count": len(proposal.candidate_ids),
            "source_types": proposal.diagnostics["source_types"],
            "source_count": proposal.diagnostics["source_count"],
            "has_email": proposal.diagnostics["candidate_has_primary_email"],
            "has_phone": proposal.diagnostics["candidate_has_primary_phone"],
            "has_tax_id": proposal.diagnostics["candidate_has_tax_id"],
            "document_count": proposal.diagnostics["document_count"],
            "why_insufficient": proposal.diagnostics["why_insufficient"],
        }
        for proposal in selected
    ]


def _mask_name(value: str) -> str:
    if "@" in value:
        local, _, domain = value.partition("@")
        return f"{local[:1]}***@{domain}"
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) >= 9:
        return f"***-***-{digits[-3:]}"
    if "." in value:
        stem, separator, extension = value.rpartition(".")
        return f"{stem[:1]}***{separator}{extension}"
    return value[:1] + "***"


if __name__ == "__main__":
    main()
