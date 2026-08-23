import json
from pathlib import Path


FIXTURE = Path(__file__).parent / "fixtures" / "unified_assistant_contract_v1.json"


def test_claims_are_typed_and_bound_to_allowlisted_sources():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    allowed = {item["source_ref"] for item in payload["sources"]}
    claim_ids = {item["claim_id"] for item in payload["claims"]}
    assert payload["schema"] == "NEXT_STABIL_UNIFIED_ASSISTANT_RESULT_V1"
    assert all(item["class"] in {"FACT", "ESTIMATE", "HYPOTHESIS", "MISSING"} for item in payload["claims"])
    assert all(set(item["source_refs"]) <= allowed for item in payload["claims"])
    assert all(set(item["supports_claim_ids"]) <= claim_ids for item in payload["sources"])


def test_estimate_has_provenance_uncertainty_and_missing_inputs():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    estimate = payload["estimate"]
    claim_ids = {item["claim_id"] for item in payload["claims"]}
    assert estimate["claim_id"] in claim_ids
    assert estimate["confidence"] in {"HIGH", "MEDIUM", "LOW", "NOT_ESTIMABLE"}
    assert estimate["basis_claim_ids"]
    assert estimate["assumptions"]
    assert estimate["missing_inputs"]


def test_source_inspector_contains_used_evidence_not_identity_dump():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert all({"source_type", "title", "excerpt", "why_used", "supports_claim_ids"} <= set(item) for item in payload["sources"])
    assert "email" not in serialized
    assert "telefon" not in serialized
    assert "address" not in serialized
