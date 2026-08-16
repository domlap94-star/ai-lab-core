from __future__ import annotations

from app.services.local_ollama_client_reconstruction_service import (
    EXPANDED_CONTEXT,
    LocalOllamaClientReconstructionService,
    LocalOllamaStructuredOutputError,
    MIN_OUTPUT_RESERVE,
    NORMAL_CONTEXT,
    ReconstructionPromptTooLargeError,
    dynamic_proposal_schema,
    select_context,
)
from test_ai_client_reconstruction import packet, proposal


def verify_local_ollama_adapter() -> None:
    captured = {}
    body = {
        "message": {"role": "assistant", "content": proposal().model_dump_json()},
        "prompt_eval_count": 20, "eval_count": 10,
        "load_duration": 1, "prompt_eval_duration": 2,
        "eval_duration": 2_000_000_000, "total_duration": 3_000_000_000,
    }

    class Response:
        def raise_for_status(self): pass
        def json(self): return body

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            captured["url"] = url; captured["payload"] = kwargs["json"]
            return Response()

    import app.services.local_ollama_client_reconstruction_service as module
    original = module.httpx.Client
    module.httpx.Client = Client
    try:
        result, usage = LocalOllamaClientReconstructionService(
            model="existing-model", base_url="http://ollama:11434"
        ).evaluate(packet())
    finally:
        module.httpx.Client = original
    assert result.client_id == 1
    assert captured["url"] == "http://ollama:11434/api/chat"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["think"] is False
    assert captured["payload"]["options"]["temperature"] == 0
    assert captured["payload"]["options"]["num_ctx"] == NORMAL_CONTEXT
    assert captured["payload"]["options"]["num_predict"] == MIN_OUTPUT_RESERVE
    assert captured["payload"]["format"]["additionalProperties"] is False
    assert "tools" not in captured["payload"]
    assert usage["tokens_per_second"] == 5.0
    print("LOCAL OLLAMA CLIENT RECONSTRUCTION TESTS: OK")


def verify_malformed_output_preserves_private_diagnostics() -> None:
    body = {
        "message": {"content": '{"client_id": 1, "canonical_name": "cut'},
        "prompt_eval_count": 3934, "eval_count": 162,
        "eval_duration": 2_000_000_000,
    }

    class Response:
        def raise_for_status(self): pass
        def json(self): return body

    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs): return Response()

    import app.services.local_ollama_client_reconstruction_service as module
    original = module.httpx.Client
    module.httpx.Client = Client
    try:
        try:
            LocalOllamaClientReconstructionService(model="test").evaluate(packet())
        except LocalOllamaStructuredOutputError as error:
            assert error.raw_content.endswith('"cut')
            assert error.usage["input_tokens"] == 3934
            assert error.usage["output_tokens"] == 162
            assert "Invalid JSON" in error.validation_error
        else:
            raise AssertionError("malformed structured output was accepted")
    finally:
        module.httpx.Client = original


def verify_dynamic_evidence_schema() -> None:
    item = packet()
    schema = dynamic_proposal_schema(item)
    alternatives = schema["properties"]["evidence_refs"]["items"]["oneOf"]
    pairs = {(entry["properties"]["source_type"]["const"],
              entry["properties"]["source_id"]["const"]) for entry in alternatives}
    assert pairs == {("google_sheets_row", 100)}
    assert ("gmail_sender_contact", 100) not in pairs

    item["source_evidence"].append({
        "source_type": "gmail_message", "source_id": 4332,
        "current_author_excerpt": "identity",
    })
    schema = dynamic_proposal_schema(item)
    alternatives = schema["properties"]["evidence_refs"]["items"]["oneOf"]
    pairs = {(entry["properties"]["source_type"]["const"],
              entry["properties"]["source_id"]["const"]) for entry in alternatives}
    assert pairs == {("google_sheets_row", 100), ("gmail_message", 4332)}

    item["source_evidence"] = []
    evidence = dynamic_proposal_schema(item)["properties"]["evidence_refs"]
    assert evidence["items"] is False
    assert evidence["maxItems"] == 0


def verify_prompt_budget_selection_and_zero_call_rejection() -> None:
    assert select_context(NORMAL_CONTEXT - MIN_OUTPUT_RESERVE) == NORMAL_CONTEXT
    assert select_context(NORMAL_CONTEXT - MIN_OUTPUT_RESERVE + 1) == EXPANDED_CONTEXT
    try:
        select_context(EXPANDED_CONTEXT - MIN_OUTPUT_RESERVE + 1)
    except ReconstructionPromptTooLargeError as error:
        assert str(error) == "PROMPT_TOO_LARGE"
    else:
        raise AssertionError("oversized prompt was accepted")

    oversized = packet()
    oversized["source_evidence"][0]["fields"]["LARGE"] = "x" * 50000
    called = False

    class Client:
        def __init__(self, **kwargs):
            nonlocal called
            called = True

    import app.services.local_ollama_client_reconstruction_service as module
    original = module.httpx.Client
    module.httpx.Client = Client
    try:
        try:
            LocalOllamaClientReconstructionService(model="test").evaluate(oversized)
        except ReconstructionPromptTooLargeError:
            pass
        else:
            raise AssertionError("oversized request reached model path")
    finally:
        module.httpx.Client = original
    assert not called


if __name__ == "__main__":
    verify_local_ollama_adapter()
    verify_malformed_output_preserves_private_diagnostics()
    verify_dynamic_evidence_schema()
    verify_prompt_budget_selection_and_zero_call_rejection()
