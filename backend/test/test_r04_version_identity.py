from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.services.version_identity_service import (
    COMPONENT_IDENTITY_SCHEMA,
    REQUIRED_COMPONENTS,
    build_public_component_identity,
    evaluate_component_compatibility,
)


def _manifest() -> dict[str, object]:
    identities = {
        "backend": ("1.0.0", "git_sha", "a" * 40),
        "api": ("1", "contract_version", "1"),
        "database": (
            "followup_assistant_chat_history_20260829",
            "schema_revision",
            "followup_assistant_chat_history_20260829",
        ),
        "web": ("1.0.2+41", "sha256", "b" * 64),
        "windows": ("1.0.2+29", "sha256", "c" * 64),
        "android": ("1.0.2+29", "sha256", "d" * 64),
        "supervisor": ("1", "git_sha", "e" * 40),
        "gateway": ("1", "sha256", "f" * 64),
        "analysis_worker": ("1", "sha256", "1" * 64),
        "vision_worker": ("1", "sha256", "2" * 64),
    }
    return {
        "schema": COMPONENT_IDENTITY_SCHEMA,
        "release_id": "next-stabil-candidate-20260909",
        "components": {
            name: {
                "version": version,
                "identity_kind": identity_kind,
                "identity": identity,
            }
            for name, (version, identity_kind, identity) in identities.items()
        },
    }


def test_semantically_distinct_component_versions_can_be_verified() -> None:
    expected = _manifest()
    observed = deepcopy(expected)

    result = evaluate_component_compatibility(expected, observed)

    assert set(expected["components"]) == set(REQUIRED_COMPONENTS)
    assert result == {
        "status": "VERIFIED",
        "mismatches": [],
        "unverified": [],
    }


@pytest.mark.parametrize(
    ("mutation", "expected_status", "expected_field"),
    [
        ("missing_component", "UNVERIFIED", "vision_worker"),
        ("invalid_hash", "UNVERIFIED", "web.identity"),
        ("unknown_identity", "UNVERIFIED", "android.identity"),
        ("mismatched_artifact", "MISMATCH", "windows.identity"),
    ],
)
def test_incomplete_or_mismatched_evidence_never_verifies(
    mutation: str,
    expected_status: str,
    expected_field: str,
) -> None:
    expected = _manifest()
    observed = deepcopy(expected)
    components = observed["components"]

    if mutation == "missing_component":
        del components["vision_worker"]
    elif mutation == "invalid_hash":
        components["web"]["identity"] = "not-a-sha256"
    elif mutation == "unknown_identity":
        components["android"]["identity"] = "UNKNOWN"
    elif mutation == "mismatched_artifact":
        components["windows"]["identity"] = "9" * 64

    result = evaluate_component_compatibility(expected, observed)

    assert result["status"] == expected_status
    fields = result["mismatches"] + result["unverified"]
    assert expected_field in fields
    assert "not-a-sha256" not in repr(result)
    assert "9" * 64 not in repr(result)


def test_unsupported_schema_is_unverified_not_a_pass() -> None:
    expected = _manifest()
    observed = deepcopy(expected)
    observed["schema"] = "UNKNOWN_SCHEMA"

    result = evaluate_component_compatibility(expected, observed)

    assert result["status"] == "UNVERIFIED"
    assert result["unverified"] == ["schema"]


def test_evaluation_does_not_mutate_stable_or_candidate_descriptions() -> None:
    expected = _manifest()
    observed = deepcopy(expected)
    before_expected = deepcopy(expected)
    before_observed = deepcopy(observed)

    evaluate_component_compatibility(expected, observed)

    assert expected == before_expected
    assert observed == before_observed


def test_public_projection_separates_backend_api_schema_and_client_policy() -> None:
    result = build_public_component_identity(
        backend_version="1.0.0",
        api_version=1,
        database_schema_revision="followup_assistant_chat_history_20260829",
        minimum_app_version="1.0.0",
        latest_app_version="1.0.2",
        release_id="next-stabil-candidate-20260909",
        source_revision="a" * 40,
        backend_image_digest="sha256:" + "b" * 64,
        environment="production",
        debug=False,
    )

    assert result["schema"] == COMPONENT_IDENTITY_SCHEMA
    assert result["verification"] == "UNVERIFIED"
    assert result["runtime_configuration"] == "SAFE"
    assert result["backend"] == {
        "version": "1.0.0",
        "source_revision": "a" * 40,
        "image_digest": "sha256:" + "b" * 64,
    }
    assert result["api"] == {"contract_version": "1"}
    assert result["database"] == {
        "schema_revision": "followup_assistant_chat_history_20260829"
    }
    assert result["client_policy"] == {
        "minimum_version": "1.0.0",
        "latest_version": "1.0.2",
    }


def test_public_projection_preserves_unknown_and_reports_debug_review() -> None:
    result = build_public_component_identity(
        backend_version="1.0.0",
        api_version=1,
        database_schema_revision=None,
        minimum_app_version="1.0.0",
        latest_app_version="1.0.0",
        release_id=None,
        source_revision=None,
        backend_image_digest=None,
        environment="development",
        debug=True,
    )

    assert result["release_id"] == "UNKNOWN"
    assert result["backend"]["source_revision"] == "UNKNOWN"
    assert result["backend"]["image_digest"] == "UNKNOWN"
    assert result["database"]["schema_revision"] == "UNKNOWN"
    assert result["runtime_configuration"] == "REVIEW_REQUIRED"


def test_real_version_endpoint_is_additive_and_has_no_startup_side_effects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.main as main_module

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("version read started a runtime dependency")

    for name in (
        "init_database",
        "start_vision_dispatcher",
        "start_knowledge_base_dispatcher",
        "start_backup_plan_reconciler",
        "start_document_preparation_dispatcher",
        "start_assistant_run_dispatcher",
    ):
        monkeypatch.setattr(main_module, name, forbidden)

    monkeypatch.setattr(main_module.settings, "release_id", None)
    monkeypatch.setattr(main_module.settings, "source_revision", None)
    monkeypatch.setattr(main_module.settings, "backend_image_digest", None)
    monkeypatch.setattr(main_module.settings, "database_schema_revision", None)

    response = TestClient(main_module.app).get("/version")
    result = response.json()

    assert response.status_code == 200
    assert {
        "application",
        "version",
        "api_version",
        "environment",
        "debug",
        "minimum_app_version",
        "latest_app_version",
    }.issubset(result)
    assert result["component_identity"]["verification"] == "UNVERIFIED"
    forbidden_keys = {
        "path",
        "command",
        "environment_variables",
        "host_inventory",
        "secret",
    }
    assert forbidden_keys.isdisjoint(result["component_identity"])
