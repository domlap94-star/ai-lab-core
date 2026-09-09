from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


COMPONENT_IDENTITY_SCHEMA = "NEXT_STABIL_COMPONENT_COMPATIBILITY_V1"
REQUIRED_COMPONENTS = (
    "backend",
    "api",
    "database",
    "web",
    "windows",
    "android",
    "supervisor",
    "gateway",
    "analysis_worker",
    "vision_worker",
)

_UNKNOWN_VALUES = frozenset({"", "UNKNOWN", "NOT_BUILT", "NOT_OBSERVED"})
_SAFE_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}")
_GIT_SHA_RE = re.compile(r"[0-9a-fA-F]{40}")
_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")
_REPO_DIGEST_RE = re.compile(r"sha256:[0-9a-fA-F]{64}")
_CONTRACT_VERSION_RE = re.compile(r"[0-9]+")


def _safe_token(value: object) -> str:
    if not isinstance(value, str):
        return "UNKNOWN"
    candidate = value.strip()
    if candidate in _UNKNOWN_VALUES or _SAFE_TOKEN_RE.fullmatch(candidate) is None:
        return "UNKNOWN"
    return candidate


def _identity_is_valid(kind: str, value: object) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    if candidate in _UNKNOWN_VALUES:
        return False
    validators = {
        "git_sha": _GIT_SHA_RE,
        "sha256": _SHA256_RE,
        "repo_digest": _REPO_DIGEST_RE,
        "schema_revision": _SAFE_TOKEN_RE,
        "contract_version": _CONTRACT_VERSION_RE,
    }
    validator = validators.get(kind)
    return validator is not None and validator.fullmatch(candidate) is not None


def _component_record(
    manifest: Mapping[str, Any],
    component: str,
) -> Mapping[str, Any] | None:
    components = manifest.get("components")
    if not isinstance(components, Mapping):
        return None
    record = components.get(component)
    return record if isinstance(record, Mapping) else None


def evaluate_component_compatibility(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> dict[str, object]:
    """Compare independently evidenced components without exposing identities.

    Component version numbers are intentionally compared only to the matching
    component. They are not required to equal one another across the release.
    """

    mismatches: set[str] = set()
    unverified: set[str] = set()

    if (
        expected.get("schema") != COMPONENT_IDENTITY_SCHEMA
        or observed.get("schema") != COMPONENT_IDENTITY_SCHEMA
    ):
        unverified.add("schema")
        return {
            "status": "UNVERIFIED",
            "mismatches": [],
            "unverified": ["schema"],
        }

    expected_release = _safe_token(expected.get("release_id"))
    observed_release = _safe_token(observed.get("release_id"))
    if "UNKNOWN" in {expected_release, observed_release}:
        unverified.add("release_id")
    elif expected_release != observed_release:
        mismatches.add("release_id")

    for component in REQUIRED_COMPONENTS:
        expected_record = _component_record(expected, component)
        observed_record = _component_record(observed, component)
        if expected_record is None or observed_record is None:
            unverified.add(component)
            continue

        expected_version = _safe_token(expected_record.get("version"))
        observed_version = _safe_token(observed_record.get("version"))
        if "UNKNOWN" in {expected_version, observed_version}:
            unverified.add(f"{component}.version")
        elif expected_version != observed_version:
            mismatches.add(f"{component}.version")

        expected_kind = _safe_token(expected_record.get("identity_kind"))
        observed_kind = _safe_token(observed_record.get("identity_kind"))
        expected_identity = expected_record.get("identity")
        observed_identity = observed_record.get("identity")

        if not _identity_is_valid(expected_kind, expected_identity):
            unverified.add(f"{component}.identity")
            continue
        if not _identity_is_valid(observed_kind, observed_identity):
            unverified.add(f"{component}.identity")
            continue
        if expected_kind != observed_kind:
            mismatches.add(f"{component}.identity_kind")
        elif expected_identity != observed_identity:
            mismatches.add(f"{component}.identity")

    status = "MISMATCH" if mismatches else "UNVERIFIED" if unverified else "VERIFIED"
    return {
        "status": status,
        "mismatches": sorted(mismatches),
        "unverified": sorted(unverified),
    }


def build_public_component_identity(
    *,
    backend_version: object,
    api_version: object,
    database_schema_revision: object,
    minimum_app_version: object,
    latest_app_version: object,
    release_id: object,
    source_revision: object,
    backend_image_digest: object,
    environment: object,
    debug: bool,
) -> dict[str, object]:
    """Build the allowlisted public projection; it is not independent proof."""

    source = (
        source_revision.strip()
        if isinstance(source_revision, str)
        and _GIT_SHA_RE.fullmatch(source_revision.strip()) is not None
        else "UNKNOWN"
    )
    image = (
        backend_image_digest.strip()
        if isinstance(backend_image_digest, str)
        and _REPO_DIGEST_RE.fullmatch(backend_image_digest.strip()) is not None
        else "UNKNOWN"
    )
    environment_value = _safe_token(environment)

    return {
        "schema": COMPONENT_IDENTITY_SCHEMA,
        "release_id": _safe_token(release_id),
        # This endpoint is a self-description. External manifest comparison is
        # required before the set may be called VERIFIED.
        "verification": "UNVERIFIED",
        "runtime_configuration": (
            "SAFE"
            if environment_value.lower() == "production" and not debug
            else "REVIEW_REQUIRED"
        ),
        "backend": {
            "version": _safe_token(backend_version),
            "source_revision": source,
            "image_digest": image,
        },
        "api": {"contract_version": _safe_token(str(api_version))},
        "database": {
            "schema_revision": _safe_token(database_schema_revision),
        },
        "client_policy": {
            "minimum_version": _safe_token(minimum_app_version),
            "latest_version": _safe_token(latest_app_version),
        },
    }
