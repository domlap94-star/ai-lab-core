from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from sqlalchemy import text

from app.core.config import settings
from app.database.session import SessionLocal
from app.services.client_notes_email_cleanup_dry_run_service import (
    ClientNotesEmailCleanupDryRunService,
)


REPORT_DIR = Path(__file__).resolve().parent / "reports"
SAFE_MANIFEST_PATH = REPORT_DIR / "client_notes_email_cleanup_safe_manifest.json"
IMPACT_PATH = REPORT_DIR / "client_notes_cleanup_downstream_impact.jsonl"
SUMMARY_PATH = REPORT_DIR / "client_notes_cleanup_downstream_summary.json"
SUMMARY_TEXT_PATH = REPORT_DIR / "client_notes_cleanup_downstream_summary.txt"
EXPECTED_6C_MANIFEST_SHA256 = (
    "f3ba677f2613cb97ab0bc3a50495df6198149e35b04221b211c3c138307e7f09"
)


DEPENDENCY_MATRIX = [
    {
        "consumer": "Client detail and list API",
        "file_function": "schemas/client.py ClientRead; api/clients/router.py",
        "reads_client_notes": True,
        "purpose": "Serialize nullable notes in the existing ClientRead contract",
        "kind": "RUNTIME",
        "legacy_email_content_required": False,
        "alternative_source_exists": True,
        "impact": "LOW",
        "action_required": "Keep notes nullable; API shape remains unchanged",
    },
    {
        "consumer": "Current Flutter Client 360 Notes",
        "file_function": "client.dart displayNotes/addressFromNotes; client_details_page.dart",
        "reads_client_notes": True,
        "purpose": "Display notes and legacy address fallback",
        "kind": "RUNTIME",
        "legacy_email_content_required": False,
        "alternative_source_exists": True,
        "impact": "LOW",
        "action_required": "None for current source; SAFE notes contain no address marker",
    },
    {
        "consumer": "Current Flutter Client Email History",
        "file_function": "ClientEmailsPanel -> /clients/{id}/emails",
        "reads_client_notes": False,
        "purpose": "Display canonical sourced Gmail history and attachments",
        "kind": "RUNTIME",
        "legacy_email_content_required": False,
        "alternative_source_exists": True,
        "impact": "NONE",
        "action_required": "None",
    },
    {
        "consumer": "Stable Android/Windows 1.0.1+4",
        "file_function": "published commit 9d8836c ClientWorkspacePanels/Client detail",
        "reads_client_notes": True,
        "purpose": "Notes display; Mail panel is still a placeholder",
        "kind": "RUNTIME",
        "legacy_email_content_required": True,
        "alternative_source_exists": False,
        "impact": "BLOCKING",
        "action_required": "Publish and verify a native release with Email History, then raise the supported minimum/gate cleanup",
    },
    {
        "consumer": "Client list search",
        "file_function": "ClientRepository._filtered_query",
        "reads_client_notes": False,
        "purpose": "Search name/legal/tax/email/phone/city",
        "kind": "RUNTIME",
        "legacy_email_content_required": False,
        "alternative_source_exists": False,
        "impact": "NONE",
        "action_required": "None",
    },
    {
        "consumer": "Flutter location filter",
        "file_function": "client_list_filter.dart filterAndSortClients",
        "reads_client_notes": True,
        "purpose": "Use only explicit Adres: fallback lines",
        "kind": "RUNTIME",
        "legacy_email_content_required": False,
        "alternative_source_exists": True,
        "impact": "NONE",
        "action_required": "None; every SAFE record is transcript-only and has no Adres: line",
    },
    {
        "consumer": "Document search",
        "file_function": "DocumentRepository._apply_read_filters",
        "reads_client_notes": False,
        "purpose": "Search document/client/candidate metadata",
        "kind": "RUNTIME",
        "legacy_email_content_required": False,
        "alternative_source_exists": True,
        "impact": "NONE",
        "action_required": "None",
    },
    {
        "consumer": "Semantic retrieval and RAG",
        "file_function": "DocumentChunkingService -> EmbeddingService -> Qdrant -> SemanticSearchService -> RagService",
        "reads_client_notes": False,
        "purpose": "Retrieve DocumentChunk content only",
        "kind": "RUNTIME",
        "legacy_email_content_required": False,
        "alternative_source_exists": False,
        "impact": "NONE",
        "action_required": "None",
    },
    {
        "consumer": "Candidate import and promotion",
        "file_function": "ImportIngestService; ClientCandidatePromotionService",
        "reads_client_notes": False,
        "purpose": "Read/write ClientCandidate.notes when importing or creating a new client",
        "kind": "RUNTIME",
        "legacy_email_content_required": False,
        "alternative_source_exists": True,
        "impact": "NONE",
        "action_required": "None for existing SAFE Client.notes",
    },
    {
        "consumer": "Exports and reports",
        "file_function": "Repository-wide audit",
        "reads_client_notes": False,
        "purpose": "No production Client.notes export/report consumer found",
        "kind": "NONE_FOUND",
        "legacy_email_content_required": False,
        "alternative_source_exists": True,
        "impact": "NONE",
        "action_required": "None",
    },
    {
        "consumer": "Active n8n workflow",
        "file_function": "Runtime read-only workflow export; import transform nodes",
        "reads_client_notes": False,
        "purpose": "Build candidate import notes; no Client API notes read",
        "kind": "RUNTIME_VERIFIED",
        "legacy_email_content_required": False,
        "alternative_source_exists": True,
        "impact": "NONE",
        "action_required": "None",
    },
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _postgres_audit(db, safe_ids: list[int]) -> dict[str, Any]:
    params = {"safe_ids": safe_ids}
    scalar_queries = {
        "document_legacy_marker_rows": (
            "SELECT COUNT(*) FROM documents "
            "WHERE extracted_text ILIKE '%Kierunek wiadomości:%'"
        ),
        "document_legacy_marker_safe_clients": (
            "SELECT COUNT(DISTINCT client_id) FROM documents "
            "WHERE client_id = ANY(:safe_ids) "
            "AND extracted_text ILIKE '%Kierunek wiadomości:%'"
        ),
        "chunk_legacy_marker_rows": (
            "SELECT COUNT(*) FROM document_chunks "
            "WHERE content ILIKE '%Kierunek wiadomości:%'"
        ),
        "chunk_legacy_marker_safe_clients": (
            "SELECT COUNT(DISTINCT d.client_id) "
            "FROM document_chunks dc JOIN documents d ON d.id=dc.document_id "
            "WHERE d.client_id = ANY(:safe_ids) "
            "AND dc.content ILIKE '%Kierunek wiadomości:%'"
        ),
        "document_client_notes_metadata_rows": (
            "SELECT COUNT(*) FROM documents "
            "WHERE metadata_raw::text ILIKE '%client_notes%' "
            "OR metadata_normalized::text ILIKE '%client_notes%'"
        ),
        "other_notes_columns": (
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema='public' AND column_name ILIKE '%notes%' "
            "AND table_name NOT IN ('clients','client_candidates')"
        ),
    }
    result = {
        name: int(db.execute(text(sql), params).scalar() or 0)
        for name, sql in scalar_queries.items()
    }
    source_row = db.execute(
        text(
            "SELECT COUNT(DISTINCT cc.matched_client_id), COUNT(*), "
            "COUNT(*) FILTER (WHERE cs.external_id IS NULL OR btrim(cs.external_id)=''), "
            "COUNT(*) FILTER (WHERE cs.raw_payload IS NULL) "
            "FROM candidate_sources cs "
            "JOIN client_candidates cc ON cc.id=cs.candidate_id "
            "WHERE cs.source_type='gmail_message' AND cs.deleted_at IS NULL "
            "AND cc.deleted_at IS NULL "
            "AND cc.status IN ('accepted','merged','duplicate') "
            "AND cc.matched_client_id = ANY(:safe_ids)"
        ),
        params,
    ).one()
    result["safe_clients_with_active_gmail"] = int(source_row[0])
    result["active_linked_gmail_sources"] = int(source_row[1])
    result["gmail_sources_missing_external_id"] = int(source_row[2])
    result["gmail_sources_missing_raw_payload"] = int(source_row[3])

    attachment_row = db.execute(
        text(
            "SELECT "
            "COUNT(*) FILTER (WHERE d.client_id = ANY(:safe_ids)), "
            "COUNT(*) FILTER (WHERE d.client_id IS NULL "
            "AND cc.matched_client_id = ANY(:safe_ids) "
            "AND cc.deleted_at IS NULL "
            "AND cc.status IN ('accepted','merged','duplicate')), "
            "COUNT(DISTINCT d.gmail_message_id) FILTER (WHERE "
            "d.client_id = ANY(:safe_ids) OR (d.client_id IS NULL "
            "AND cc.matched_client_id = ANY(:safe_ids) "
            "AND cc.deleted_at IS NULL "
            "AND cc.status IN ('accepted','merged','duplicate'))) "
            "FROM documents d LEFT JOIN client_candidates cc ON cc.id=d.candidate_id "
            "WHERE d.source_type='gmail_attachment'"
        ),
        params,
    ).one()
    result["direct_safe_attachment_documents"] = int(attachment_row[0])
    result["candidate_safe_attachment_documents"] = int(attachment_row[1])
    result["safe_attachment_message_ids"] = int(attachment_row[2])
    return result


def _qdrant_audit(safe_ids: set[int]) -> dict[str, Any]:
    client = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout=60,
    )
    collection = settings.qdrant_document_chunks_collection
    if not client.collection_exists(collection):
        return {
            "collection_exists": False,
            "point_count": 0,
            "notes_payload_keys": 0,
            "legacy_marker_points": 0,
            "legacy_marker_safe_clients": 0,
            "writes": 0,
        }

    offset = None
    total = 0
    note_keys = 0
    marker_points = 0
    marker_safe_clients: set[int] = set()
    source_types: Counter[str] = Counter()
    content_sources: Counter[str] = Counter()
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            total += 1
            payload = dict(point.payload or {})
            source_types[str(payload.get("source_type"))] += 1
            content_sources[str(payload.get("content_source"))] += 1
            if any(
                str(key).casefold() in {"notes", "client_notes", "crm_notes"}
                for key in payload
            ):
                note_keys += 1
            if "kierunek wiadomości:" in str(payload.get("content") or "").casefold():
                marker_points += 1
                client_id = payload.get("client_id")
                if isinstance(client_id, int) and client_id in safe_ids:
                    marker_safe_clients.add(client_id)
        if offset is None:
            break
    return {
        "collection_exists": True,
        "point_count": int(client.count(collection_name=collection, exact=True).count),
        "scrolled_points": total,
        "source_types": dict(source_types),
        "content_sources": dict(content_sources),
        "notes_payload_keys": note_keys,
        "legacy_marker_points": marker_points,
        "legacy_marker_safe_clients": len(marker_safe_clients),
        "writes": 0,
    }


def build_audit(
    *,
    native_email_history_available: bool,
    n8n_client_notes_reads: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_hash = _sha256(SAFE_MANIFEST_PATH)
    if manifest_hash != EXPECTED_6C_MANIFEST_SHA256:
        raise RuntimeError(
            "CHUNK 6C safe manifest drift: "
            f"expected={EXPECTED_6C_MANIFEST_SHA256}, actual={manifest_hash}"
        )
    manifest = json.loads(SAFE_MANIFEST_PATH.read_text(encoding="utf-8"))
    safe_manifest = {
        int(row["client_id"]): row for row in manifest.get("records", [])
    }

    db = SessionLocal()
    try:
        db.execute(text("SET TRANSACTION READ ONLY"))
        proposals, six_c_summary = ClientNotesEmailCleanupDryRunService(db).run()
        safe_proposals = {
            item.client_id: item
            for item in proposals
            if item.classification in {
                "SAFE_REMOVE_TRANSCRIPT_ONLY",
                "SAFE_CLEAR_NOTES",
            }
        }
        current_signature = {
            client_id: (
                item.before_sha256,
                item.proposed_notes_sha256,
                item.classification,
            )
            for client_id, item in safe_proposals.items()
        }
        manifest_signature = {
            client_id: (
                row["expected_before_sha256"],
                row["proposed_after_sha256"],
                row["classification"],
            )
            for client_id, row in safe_manifest.items()
        }
        if current_signature != manifest_signature:
            raise RuntimeError("CHUNK 6C safe manifest records drifted")
        postgres = _postgres_audit(db, sorted(safe_proposals))
        db.rollback()
    finally:
        db.close()

    qdrant = _qdrant_audit(set(safe_proposals))
    safe_blocks = sum(item.removed_block_count for item in safe_proposals.values())
    source_backed_blocks = sum(
        status == "CONFIRMED_SOURCE_MATCH"
        for item in safe_proposals.values()
        for status in item.source_match_statuses
    )
    source_anomalies = safe_blocks - source_backed_blocks
    vector_dependency = bool(
        qdrant["notes_payload_keys"]
        or qdrant["legacy_marker_points"]
        or postgres["chunk_legacy_marker_rows"]
    )
    native_block = not native_email_history_available
    automation_block = n8n_client_notes_reads > 0

    records = []
    for client_id, item in sorted(safe_proposals.items()):
        reasons = []
        if native_block:
            reasons.append("DEPLOYED_NATIVE_1_0_1_PLUS_4_HAS_MAIL_PLACEHOLDER")
        if automation_block:
            reasons.append("ACTIVE_N8N_READS_CLIENT_NOTES")
        if vector_dependency:
            reasons.append("STALE_VECTOR_DEPENDENCY")
        if source_anomalies:
            reasons.append("EMAIL_SOURCE_INTEGRITY_ANOMALY")
        records.append(
            {
                "client_id": client_id,
                "before_notes_sha256": item.before_sha256,
                "safe_classification": item.classification,
                "gmail_history_present": True,
                "all_blocks_source_confirmed": all(
                    status == "CONFIRMED_SOURCE_MATCH"
                    for status in item.source_match_statuses
                ),
                "client_api_dependency": "SERIALIZED_NULLABLE_UI_NOTES",
                "search_dependency": "NONE",
                "rag_dependency": "NONE",
                "vector_dependency": "NONE" if not vector_dependency else "PRESENT",
                "export_dependency": "NONE_FOUND_IN_REPOSITORY",
                "automation_dependency": (
                    "NONE_RUNTIME_VERIFIED"
                    if not automation_block
                    else "ACTIVE_CLIENT_NOTES_READ"
                ),
                "attachment_dependency": "NONE",
                "blocking_dependency": reasons,
                "recommended_action": (
                    "BLOCK_6D_UNTIL_NATIVE_EMAIL_HISTORY_RELEASE_AND_SUPPORT_GATE"
                    if reasons
                    else "ELIGIBLE_FOR_HUMAN_APPROVAL_REQUEST"
                ),
            }
        )

    blocking_clients = sum(bool(row["blocking_dependency"]) for row in records)
    go_no_go = (
        "BLOCK_6D"
        if blocking_clients or source_anomalies or vector_dependency
        else "CLEAR_TO_REQUEST_HUMAN_APPROVAL_FOR_6D"
    )
    summary = {
        "six_c_recheck": {
            "manifest_sha256": manifest_hash,
            "manifest_stable": True,
            "safe_records": len(records),
            "transcript_like_clients": six_c_summary["baseline"][
                "transcript_like_notes"
            ],
            "safe_clear_notes": six_c_summary["classification"]["SAFE_CLEAR_NOTES"],
            "review_required": six_c_summary["classification"]["REVIEW_REQUIRED"],
            "blocked_no_source_history": six_c_summary["classification"][
                "BLOCKED_NO_SOURCE_HISTORY"
            ],
            "safe_legacy_blocks": safe_blocks,
            "safe_confirmed_source_matches": source_backed_blocks,
        },
        "dependency_matrix": DEPENDENCY_MATRIX,
        "dependency_counts": {
            "no_dependency": 0,
            "ui_only_redundancy": len(records),
            "search_dependency": 0,
            "rag_dependency": 0,
            "vector_dependency": len(records) if vector_dependency else 0,
            "export_dependency": 0,
            "automation_dependency": len(records) if automation_block else 0,
            "other": 0,
        },
        "blocking": {
            "clients_blocked": blocking_clients,
            "reason_categories": sorted(
                {reason for row in records for reason in row["blocking_dependency"]}
            ),
        },
        "functional_coverage": {
            "fully_preserved": len(records) if not blocking_clients else 0,
            "partially_preserved": 0,
            "unknown": 0,
            "degraded": blocking_clients,
        },
        "email_source_integrity": {
            "safe_clients": len(records),
            "safe_blocks": safe_blocks,
            "source_backed_blocks": source_backed_blocks,
            "missing_sources": source_anomalies,
            "linkage_anomalies": (
                len(records) - postgres["safe_clients_with_active_gmail"]
            ),
            "active_linked_gmail_sources": postgres["active_linked_gmail_sources"],
            "normalization_anomalies": 0,
        },
        "postgres_document_chunk_audit": postgres,
        "qdrant_audit": qdrant,
        "n8n_audit": {
            "runtime_verified": True,
            "active_workflows": 1,
            "client_notes_read_consumers": n8n_client_notes_reads,
            "notes_usage": "candidate import payload construction only",
        },
        "deployed_native_audit": {
            "stable_version": "1.0.1+4",
            "published_commit": "9d8836ca53cb3cd53fdbadcb928935572a73490f",
            "email_history_source_commit": "4b73ad4b21e0346c0af4bd4f9aa41d3b9dcba47c",
            "email_history_available": native_email_history_available,
            "notes_display_available": True,
            "impact": "BLOCKING" if native_block else "NONE",
        },
        "recovery_readiness": {
            "six_c_before_hashes_available": True,
            "safe_full_old_notes_snapshot_available": False,
            "old_database_dumps_found": 2,
            "restore_tested": False,
            "required_before_apply": (
                "Create encrypted/private local rollback snapshot containing "
                "client_id, expected_before_sha256 and full old notes"
            ),
        },
        "information_loss_risk": (
            "HIGH_FOR_DEPLOYED_NATIVE_UI; NONE_FOR_CANONICAL_GMAIL_STORAGE"
            if native_block
            else "LOW"
        ),
        "duplication_quality_effect": "NEUTRAL_FOR_RAG",
        "go_no_go": go_no_go,
        "required_prerequisites": (
            [
                "Publish and human-verify Android/Windows Email History release",
                "Gate cleanup on a minimum supported native version containing Email History",
                "Create encrypted/private full-notes rollback snapshot immediately before apply",
                "Re-run 6C and 6C.1 without manifest/source drift",
            ]
            if native_block
            else [
                "Create encrypted/private full-notes rollback snapshot immediately before apply",
                "Re-run 6C and 6C.1 without manifest/source drift",
            ]
        ),
        "production_database_writes": 0,
        "qdrant_writes": 0,
    }
    return records, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--native-email-history",
        choices=("available", "unavailable"),
        required=True,
    )
    parser.add_argument("--n8n-client-notes-reads", type=int, required=True)
    args = parser.parse_args()
    records, summary = build_audit(
        native_email_history_available=args.native_email_history == "available",
        n8n_client_notes_reads=args.n8n_client_notes_reads,
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    IMPACT_PATH.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records),
        encoding="utf-8",
    )
    _write_json(SUMMARY_PATH, summary)
    SUMMARY_TEXT_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "6C RECHECK: "
        f"safe={len(records)}, blocks={summary['email_source_integrity']['safe_blocks']}, "
        f"source_backed={summary['email_source_integrity']['source_backed_blocks']}"
    )
    print(
        "DOWNSTREAM: "
        f"blocking={summary['blocking']['clients_blocked']}, "
        f"qdrant_notes={summary['qdrant_audit']['notes_payload_keys']}, "
        f"n8n_notes_reads={summary['n8n_audit']['client_notes_read_consumers']}"
    )
    print(f"SAFE CLIENTS RECHECKED: {len(records)}")
    print(f"GO / NO-GO: {summary['go_no_go']}")
    print("PRODUCTION DATABASE WRITES: 0")
    print("QDRANT WRITES: 0")


if __name__ == "__main__":
    main()
