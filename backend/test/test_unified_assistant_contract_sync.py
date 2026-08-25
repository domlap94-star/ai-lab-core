from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.unified_assistant import UnifiedAssistantRequest


FIXTURE = Path(__file__).parent / "fixtures" / "unified_assistant_current_android_requests.json"


def _cases() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["case"])
def test_current_android_request_shape_validates_against_fastapi_schema(case: dict) -> None:
    payload = case["request"]
    parsed = UnifiedAssistantRequest.model_validate(payload)
    assert parsed.model_dump(exclude_none=True) == payload


def test_current_android_fixture_still_fails_closed_on_unknown_field() -> None:
    payload = dict(_cases()[0]["request"], unsupported_mobile_field=True)
    with pytest.raises(ValidationError) as captured:
        UnifiedAssistantRequest.model_validate(payload)
    assert captured.value.errors()[0]["type"] == "extra_forbidden"
