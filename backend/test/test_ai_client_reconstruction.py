from __future__ import annotations

from types import SimpleNamespace

from app.schemas.client_reconstruction import ClientReconstructionProposal
from app.services.client_identity_name_quality_service import ClientIdentityNameQualityService
from app.services.client_reconstruction_policy_service import ClientReconstructionPolicyService
from app.services.openai_client_reconstruction_service import SYSTEM_INSTRUCTION
from app.services.openai_client_reconstruction_service import OpenAIClientReconstructionService


class EmptyQuery:
    def filter(self, *args, **kwargs): return self
    def all(self): return []


class EmptySession:
    def query(self, *args, **kwargs): return EmptyQuery()


def packet(values=None, *, client_id=1, projection_status="projected"):
    return {
        "client": {"id": client_id, "name": "person@example.com"},
        "candidate_links": [{"candidate_id": 10, "status": "accepted", "source_ids": [100]}],
        "deterministic_projections": [{
            "candidate_id": 10, "projection_status": projection_status,
            "entity_name": "Jan Kowalski", "legal_name": None,
            "contact_name": "Jan Kowalski", "contact_email": "jan@example.com",
            "contact_phone": "+48 500 600 700", "evidence": [{"value": "Jan Kowalski"}],
        }],
        "source_evidence": [{"source_id": 100, "source_type": "google_sheets_row",
                             "fields": values or {"IMIĘ": "Jan", "NAZWISKO": "Kowalski"}}],
    }


def proposal(**overrides):
    values = {
        "client_id": 1, "entity_type": "person", "canonical_name": "Jan Kowalski",
        "canonical_legal_name": None, "canonical_email": "jan@example.com",
        "canonical_phone": "+48 500 600 700", "current_name_class": "email_artifact",
        "proposed_name_transformation": "exact_source_value", "confidence": 0.98,
        "evidence_refs": [{"source_type": "google_sheets_row", "source_id": 100, "field": "IMIĘ+NAZWISKO"}],
        "conflict_detected": False, "duplicate_risk": False,
        "recommended_disposition": "PROPOSE_REPAIR",
    }
    values.update(overrides)
    return ClientReconstructionProposal.model_validate(values)


def test_supported_exact_identity_is_high_confidence_candidate():
    result = ClientReconstructionPolicyService(EmptySession()).validate(packet(), proposal())
    assert result.classification == "HIGH_CONFIDENCE_REPAIR_CANDIDATE"


def test_hallucinated_name_is_model_invalid():
    result = ClientReconstructionPolicyService(EmptySession()).validate(
        packet(), proposal(canonical_name="Invented Person")
    )
    assert result.classification == "MODEL_INVALID"
    assert "unsupported canonical_name" in result.validation_errors


def test_foreign_evidence_reference_is_invalid():
    result = ClientReconstructionPolicyService(EmptySession()).validate(
        packet(), proposal(evidence_refs=[{"source_type": "gmail_message", "source_id": 999, "field": "from"}])
    )
    assert result.classification == "MODEL_INVALID"


def test_identity_artifacts_are_policy_rejected():
    service = ClientReconstructionPolicyService(EmptySession())
    cases = [
        ("a@example.com", "email_artifact"), ("500 600 700", "phone_artifact"),
        ("[2.PNG]", "filename_artifact"), ("Warszawa ul. Długa", "address_artifact"),
        (">>>", "garbage_artifact"), ("Oferta wysłana", "status_or_note_artifact"),
    ]
    for value, artifact in cases:
        item = packet({"NAZWA": value})
        item["deterministic_projections"][0]["entity_name"] = value
        item["deterministic_projections"][0]["contact_name"] = value
        item["deterministic_projections"][0]["evidence"] = [{"value": value}]
        result = service.validate(item, proposal(canonical_name=value, canonical_email=None,
                                                  canonical_phone=None, current_name_class=artifact))
        assert result.classification == "POLICY_REJECTED", value


def test_first_party_relay_and_quoted_history_are_not_authoritative():
    service = ClientReconstructionPolicyService(EmptySession())
    for state in ("first_party_internal", "relay_container"):
        item = packet(projection_status=state)
        item["deterministic_projections"][0].update(entity_name=None, contact_name=None, evidence=[])
        result = service.validate(item, proposal(canonical_name="Jan Kowalski", canonical_email=None,
                                                  canonical_phone=None))
        assert result.classification == "MODEL_INVALID"
    assert "untrusted data" in SYSTEM_INSTRUCTION
    assert "prior instructions" in SYSTEM_INSTRUCTION


def test_phone_email_normalization_and_composed_name():
    service = ClientReconstructionPolicyService(EmptySession())
    result = service.validate(packet(), proposal(proposed_name_transformation="compose_person_name",
                                                  canonical_email="JAN@EXAMPLE.COM",
                                                  canonical_phone="500-600-700"))
    assert result.classification == "HIGH_CONFIDENCE_REPAIR_CANDIDATE"


def test_quality_guards_cover_required_artifacts():
    quality = ClientIdentityNameQualityService
    assert quality.suspicion_types("x@example.com") == ("EMAIL_AS_NAME",)
    assert "PHONE_AS_NAME" in quality.suspicion_types("500 600 700")
    assert "FILE_AS_NAME" in quality.suspicion_types("[2.PNG]")
    assert "ADDRESS_OR_LOCATION_AS_NAME" in quality.additional_findings("Pruszków ul. Guzikowa")


def test_responses_request_is_private_strict_and_toolless(monkeypatch=None):
    captured = {}
    response_body = {"output_text": proposal().model_dump_json(),
                     "usage": {"input_tokens": 10, "output_tokens": 5}}

    class Response:
        def raise_for_status(self): pass
        def json(self): return response_body

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            captured.update(kwargs["json"])
            assert "Authorization" in kwargs["headers"]
            return Response()

    import app.services.openai_client_reconstruction_service as module
    original = module.httpx.Client
    module.httpx.Client = Client
    try:
        result, usage = OpenAIClientReconstructionService(api_key="private-test-value").evaluate(packet())
    finally:
        module.httpx.Client = original
    assert result.client_id == 1
    assert usage == {"input_tokens": 10, "output_tokens": 5}
    assert captured["store"] is False
    assert "tools" not in captured
    assert captured["text"]["format"]["strict"] is True


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"AI client reconstruction tests passed: {len(tests)}")
