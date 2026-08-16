from __future__ import annotations

from app.services.local_ollama_client_reconstruction_service import (
    LocalOllamaClientReconstructionService,
    LocalOllamaStructuredOutputError,
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
    assert captured["payload"]["options"] == {
        "temperature": 0,
        "num_ctx": 4096,
    }
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


if __name__ == "__main__":
    verify_local_ollama_adapter()
    verify_malformed_output_preserves_private_diagnostics()
