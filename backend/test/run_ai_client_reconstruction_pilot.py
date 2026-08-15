from __future__ import annotations

import json
import os
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.client import Client
from app.services.client_identity_name_quality_service import ClientIdentityNameQualityService
from app.services.client_reconstruction_evidence_service import ClientReconstructionEvidenceService


REPORTS = Path(__file__).resolve().parent / "reports"
HOLD_IDS = (13, 1745, 2256, 2560)
SEED = 20260815
MAX_CLIENTS = 200


def selection_class(name: str) -> str:
    quality = ClientIdentityNameQualityService
    suspicion = quality.suspicion_types(name)
    findings = quality.additional_findings(name)
    if "EMAIL_AS_NAME" in suspicion: return "email_artifact"
    if "PHONE_AS_NAME" in suspicion: return "phone_artifact"
    if "FILE_AS_NAME" in suspicion: return "filename_artifact"
    if "ADDRESS_OR_LOCATION_AS_NAME" in findings: return "address_artifact"
    if name.strip().startswith("["): return "prefix_artifact"
    if not any(character.isalnum() for character in name): return "garbage_artifact"
    if len(name.split()) == 2 and any(part.endswith(".") for part in name.split()): return "abbreviated_identity"
    return "clean_control"


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("phase1a-%Y%m%dT%H%M%SZ")
    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        clients = db.query(Client.id, Client.name).filter(Client.deleted_at.is_(None)).order_by(Client.id).all()
        groups: dict[str, list[int]] = {}
        for client_id, name in clients:
            groups.setdefault(selection_class(name), []).append(client_id)
        selected: list[tuple[int, str]] = []
        for client_id in HOLD_IDS:
            if any(row.id == client_id for row in clients): selected.append((client_id, "known_hold"))
        rng = random.Random(SEED)
        for group in sorted(key for key in groups if key != "clean_control"):
            for client_id in groups[group][:24]:
                if client_id not in {item[0] for item in selected}: selected.append((client_id, group))
        controls = list(groups.get("clean_control", [])); rng.shuffle(controls)
        for client_id in controls[:40]:
            if client_id not in {item[0] for item in selected}: selected.append((client_id, "clean_control"))
        selected = selected[:MAX_CLIENTS]
        builder = ClientReconstructionEvidenceService(db)
        records = []
        characters = 0
        for client_id, group in selected:
            packet = builder.build(client_id)
            characters += len(json.dumps(packet, ensure_ascii=False))
            records.append({"client_id": client_id, "selection_class": group,
                            "evidence_packet_sha256": builder.sha256(packet)})
        manifest = {"run_id": run_id, "seed": SEED, "selected_count": len(records), "records": records}
        (REPORTS / "ai_client_reconstruction_pilot_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        summary = {
            "run_id": run_id, "selected": len(records), "selection_breakdown": dict(Counter(item["selection_class"] for item in records)),
            "evidence_packet_characters": characters, "openai_key": "PRESENT" if settings.openai_api_key else "MISSING",
            "model": settings.openai_client_reconstruction_model, "requests": 0, "successful": 0, "failed": 0,
            "decision": "PILOT_BLOCKED_MISSING_API_KEY" if not settings.openai_api_key else "READY_TO_CALL",
        }
        (REPORTS / "ai_client_reconstruction_pilot_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (REPORTS / "ai_client_reconstruction_pilot_summary.txt").write_text("\n".join(f"{k}: {v}" for k, v in summary.items()), encoding="utf-8")
        print(json.dumps(summary))
        db.rollback()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
