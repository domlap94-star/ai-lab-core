from __future__ import annotations

from run_existing_ollama_reconstruction_calibration import (
    analyze_record,
    select_smoke_records,
    summarize,
)


CURRENT = {
    "id": 1,
    "client_type": "person",
    "name": "Jan Kowalski",
    "legal_name": None,
    "email": "jan@example.com",
    "phone": "500600700",
}


def record(
    *,
    classification: str,
    canonical_name: str | None = "Jan Kowalski",
    confidence: float = 0.98,
    errors: list[str] | None = None,
    duplicate_risk: bool = False,
    duplicate_ids: list[int] | None = None,
    conflict: bool = False,
    selection_class: str = "clean_control",
) -> dict:
    return {
        "client_id": 1,
        "selection_class": selection_class,
        "proposal": {
            "client_id": 1,
            "entity_type": "person" if canonical_name else "unknown",
            "canonical_name": canonical_name,
            "canonical_legal_name": None,
            "canonical_email": "jan@example.com" if canonical_name else None,
            "canonical_phone": "500600700" if canonical_name else None,
            "confidence": confidence,
            "evidence_refs": [{"source_type": "gmail_message", "source_id": 10, "field": "from"}],
            "duplicate_risk": duplicate_risk,
            "conflict_detected": conflict,
            "recommended_disposition": "CONFLICT" if conflict else "PROPOSE_REPAIR",
        },
        "policy": {
            "classification": classification,
            "validation_errors": errors or [],
            "duplicate_client_ids": duplicate_ids or [],
        },
        "usage": {},
        "latency_seconds": 0.1,
    }


def verify_clean_control_semantics() -> None:
    keep = analyze_record(record(classification="KEEP"), CURRENT)
    assert keep["clean_keep"] and not keep["clean_false_change"]

    abstention = analyze_record(
        record(classification="INSUFFICIENT_EVIDENCE", canonical_name=None), CURRENT
    )
    assert abstention["clean_non_keep"]
    assert abstention["clean_abstention_or_rejection"]
    assert not abstention["clean_false_change"]

    unsupported = analyze_record(
        record(
            classification="MODEL_INVALID",
            canonical_name="Invented Person",
            errors=["unsupported canonical_name"],
        ),
        CURRENT,
    )
    assert unsupported["clean_false_change"]

    foreign_only = analyze_record(
        record(
            classification="MODEL_INVALID",
            errors=["foreign evidence ref gmail_message:999"],
        ),
        CURRENT,
    )
    assert foreign_only["clean_abstention_or_rejection"]
    assert not foreign_only["clean_false_change"]


def verify_safety_bypass_metrics() -> None:
    critical = analyze_record(
        record(
            classification="HIGH_CONFIDENCE_REPAIR_CANDIDATE",
            errors=["foreign evidence ref gmail_message:999"],
        ),
        CURRENT,
    )
    assert critical["critical_policy_bypass"]
    assert critical["foreign_evidence_proposal"]
    assert critical["foreign_evidence_bypass"]

    duplicate = analyze_record(
        record(
            classification="HIGH_CONFIDENCE_REPAIR_CANDIDATE",
            duplicate_risk=True,
            duplicate_ids=[22],
        ),
        CURRENT,
    )
    assert duplicate["duplicate_risk"]
    assert duplicate["duplicate_bypass"]
    assert duplicate["critical_policy_bypass"]


def verify_proposal_vs_bypass_distinction() -> None:
    unsupported_echo = analyze_record(
        record(
            classification="MODEL_INVALID",
            errors=["unsupported canonical_name"],
        ),
        CURRENT,
    )
    assert unsupported_echo["unsupported_high_confidence_proposal"]
    assert not unsupported_echo["clean_false_change"]

    stopped = analyze_record(
        record(
            classification="MODEL_INVALID",
            canonical_name="Invented Person",
            errors=["unsupported canonical_name"],
        ),
        CURRENT,
    )
    assert stopped["unsupported_high_confidence_proposal"]
    assert not stopped["unsupported_high_confidence_bypass"]

    bypassed = analyze_record(
        record(
            classification="HIGH_CONFIDENCE_REPAIR_CANDIDATE",
            canonical_name="Invented Person",
            errors=["unsupported canonical_name"],
        ),
        CURRENT,
    )
    assert bypassed["unsupported_high_confidence_proposal"]
    assert bypassed["unsupported_high_confidence_bypass"]

    foreign_stopped = analyze_record(
        record(classification="MODEL_INVALID", errors=["foreign evidence ref gmail_message:999"]),
        CURRENT,
    )
    assert foreign_stopped["foreign_evidence_proposal"]
    assert not foreign_stopped["foreign_evidence_bypass"]


def verify_zero_high_confidence_coverage() -> None:
    item = record(classification="INSUFFICIENT_EVIDENCE", canonical_name=None)
    summary, _ = summarize(
        model="test", records=[item], failures=[], current_by_id={1: CURRENT}, run_id="test"
    )
    assert summary["high_confidence_count"] == 0
    assert summary["high_confidence_evidence_coverage"] == "N/A_NO_HIGH_CONFIDENCE_CANDIDATES"


def verify_deterministic_smoke_selection() -> None:
    records = [
        {"client_id": 1, "selection_class": "clean_control"},
        {"client_id": 2, "selection_class": "known_hold"},
        {"client_id": 3, "selection_class": "email_artifact"},
        {"client_id": 4, "selection_class": "phone_artifact"},
        {"client_id": 5, "selection_class": "abbreviated_identity"},
        {"client_id": 6, "selection_class": "garbage_artifact"},
    ]
    richness = {1: 1, 2: 2, 3: 3, 4: 99, 5: 4, 6: 5}
    first = select_smoke_records(records, richness)
    second = select_smoke_records(records, richness)
    assert [item["client_id"] for item in first] == [1, 2, 3, 4, 5]
    assert first == second


if __name__ == "__main__":
    verify_clean_control_semantics()
    verify_safety_bypass_metrics()
    verify_proposal_vs_bypass_distinction()
    verify_zero_high_confidence_coverage()
    verify_deterministic_smoke_selection()
    print("RECONSTRUCTION CALIBRATION QUALITY GATE TESTS: OK")
