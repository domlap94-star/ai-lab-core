"""Restricted entrypoint for the versioned DOC-04 Windows runtime.

Only Python's standard library is imported until the explicit working-directory
policy and the permanent dotenv audit barrier are installed.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import io
import json
import math
import ntpath
import os
import pathlib
import platform
import re
import subprocess
import sys
import unittest
from typing import Any, Iterator


SAFE_CODE = "DOC04B_RUNTIME_REFUSED"
ENV_FORBIDDEN = "DOC04_RUNTIME_ENV_FILE_FORBIDDEN"
PRODUCTION_EXPECTED_PACKAGES = {
    "SQLAlchemy": "2.0.43",
    "greenlet": "3.5.5",
    "typing-extensions": "4.16.0",
    "psycopg": "3.2.10",
    "psycopg-binary": "3.2.10",
    "pydantic": "2.11.7",
    "pydantic-core": "2.33.2",
    "annotated-types": "0.8.0",
    "typing-inspection": "0.4.4",
    "pydantic-settings": "2.11.0",
    "python-dotenv": "1.2.2",
}
FIXED_TEST_SUITES = {
    "runtime-contract": ("test.test_doc04_windows_runtime_contract",),
    "doc04a": (
        "test.test_document_metadata_unicode_safety",
        "test.test_document_metadata_surrogate_repair",
    ),
    "doc01": ("test.test_document_ingestion_vision_containment",),
    "doc02": ("test.test_document_office_archive_safety",),
    "doc03": ("test.test_document_preparation_recovery_fencing",),
    "intake": ("test.test_chunk9_document_intake",),
    "assistant": (
        "test.test_assistant_pipeline_v2_implementation",
        "test.test_android_acceptance_source_binding",
    ),
    "regression": (
        "test.test_document_ingestion_vision_containment",
        "test.test_document_office_archive_safety",
        "test.test_document_preparation_recovery_fencing",
        "test.test_document_intelligence_resource_wait",
        "test.test_chunk9_document_intake",
        "test.test_assistant_pipeline_v2_implementation",
        "test.test_android_acceptance_source_binding",
    ),
}
NONPRODUCTION_POLICIES = {
    "readiness",
    "repair-help",
    "compatibility-vectors",
    "isolated-test",
    "isolated-alembic-upgrade",
    "nonproduction-audit-probe",
    "backend-reference",
    "production-import-trace",
    "repair-relay-self-test",
}
PRODUCTION_POLICIES = {"production-preflight", "production-execute"}
SYNTHETIC_PRODUCTION_POLICY = "synthetic-production-audit"
SENSITIVE_ABSENT = {
    "OPENAI_API_KEY",
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONUSERBASE",
    "VIRTUAL_ENV",
    "PIP_CONFIG_FILE",
    "PIP_INDEX_URL",
    "PIP_EXTRA_INDEX_URL",
    "VISION_SUPERVISOR_URL",
    "BACKUP_SUPERVISOR_URL",
}
HEX40 = re.compile(r"^[0-9a-f]{40}$")
REPAIR_RESULT = re.compile(r"^DOCUMENT_METADATA_REPAIR_[A-Z0-9_]{1,96}$")
REPAIR_SUCCESS_CODES = {
    "DOCUMENT_METADATA_REPAIR_DRY_RUN",
    "DOCUMENT_METADATA_REPAIR_EXECUTED",
    "DOCUMENT_METADATA_REPAIR_PRODUCTION_PREFLIGHT_OK",
}
MAX_REPAIR_OUTPUT_BYTES = 65_536
ISOLATED_DATABASE_REVISION = "followup_assistant_chat_history_20260829"

_ENV_FILE_OPEN_ATTEMPTS = 0
_ALLOWED_ENV_FILE: str | None = None
_RESULT_FD = os.dup(1)
_ERROR_FD = os.dup(2)
_SAFE_FAILURE_DETAILS: dict[str, Any] = {}


class RuntimeRefusal(RuntimeError):
    """Bounded fail-closed runtime error."""


def _refuse(code: str = SAFE_CODE) -> None:
    raise RuntimeRefusal(code)


def _normal_path(value: str) -> str:
    return os.path.normcase(os.path.abspath(value))


def _is_within(candidate: str, boundary: str) -> bool:
    try:
        candidate_key = _normal_path(candidate)
        boundary_key = _normal_path(boundary)
        return os.path.commonpath((candidate_key, boundary_key)) == boundary_key
    except (OSError, ValueError):
        return False


def _is_drive_root(path: pathlib.Path) -> bool:
    anchor = pathlib.Path(path.anchor)
    return bool(path.anchor) and _normal_path(str(path)) == _normal_path(str(anchor))


def _is_reparse_or_link(path: pathlib.Path) -> bool:
    if path.is_symlink():
        return True
    if os.name == "nt":
        return bool(path.stat(follow_symlinks=False).st_file_attributes & 0x400)
    return False


def _assert_no_reparse_chain(path: pathlib.Path, code: str) -> None:
    cursor = pathlib.Path(os.path.abspath(path))
    while True:
        if cursor.exists() and _is_reparse_or_link(cursor):
            _refuse(code)
        parent = cursor.parent
        if parent == cursor:
            break
        cursor = parent


def _assert_regular_non_reparse_file(path: pathlib.Path, code: str) -> None:
    _assert_no_reparse_chain(path, code)
    if not path.is_file() or _is_reparse_or_link(path):
        _refuse(code)


def _path_from_audit(value: Any) -> str | None:
    if isinstance(value, int):
        return None
    try:
        raw = os.fspath(value)
    except TypeError:
        return None
    if isinstance(raw, bytes):
        try:
            return os.fsdecode(raw)
        except UnicodeError:
            return None
    return raw if isinstance(raw, str) else None


def _install_env_audit_guard(allowed_env_file: str | None) -> None:
    global _ALLOWED_ENV_FILE
    _ALLOWED_ENV_FILE = _normal_path(allowed_env_file) if allowed_env_file else None

    def audit(event: str, args: tuple[Any, ...]) -> None:
        global _ENV_FILE_OPEN_ATTEMPTS
        if event != "open" or not args:
            return
        candidate = _path_from_audit(args[0])
        if candidate is None:
            return
        if ntpath.basename(ntpath.normpath(candidate)).casefold() != ".env":
            return
        _ENV_FILE_OPEN_ATTEMPTS += 1
        candidate_key = _normal_path(candidate)
        if _ALLOWED_ENV_FILE is None or candidate_key != _ALLOWED_ENV_FILE:
            raise RuntimeRefusal(ENV_FORBIDDEN)

    sys.addaudithook(audit)


def _environment_roots() -> tuple[pathlib.Path, pathlib.Path, str]:
    policy = os.environ.get("NEXT_DOC04_RUNTIME_POLICY", "")
    if policy not in NONPRODUCTION_POLICIES | PRODUCTION_POLICIES | {SYNTHETIC_PRODUCTION_POLICY}:
        _refuse("DOC04B_RUNTIME_POLICY_REQUIRED")
    environment_raw = os.environ.get("NEXT_DOC04_ENVIRONMENT_ROOT", "")
    working_raw = os.environ.get("NEXT_DOC04_WORKING_DIRECTORY", "")
    if not environment_raw or not working_raw:
        _refuse("DOC04B_EXPLICIT_WORKING_DIRECTORY_REQUIRED")
    environment_root = pathlib.Path(environment_raw)
    working_directory = pathlib.Path(working_raw)
    for label, path in (("ENVIRONMENT_ROOT", environment_root), ("WORKING_DIRECTORY", working_directory)):
        if not path.is_absolute():
            _refuse(f"DOC04B_{label}_NOT_ABSOLUTE")
        if not path.is_dir():
            _refuse(f"DOC04B_{label}_NOT_DIRECTORY")
        if _is_drive_root(path):
            _refuse(f"DOC04B_{label}_DRIVE_ROOT")
        _assert_no_reparse_chain(path, f"DOC04B_{label}_REPARSE")
    environment_root = pathlib.Path(os.path.realpath(environment_root))
    working_directory = pathlib.Path(os.path.realpath(working_directory))
    if _normal_path(str(environment_root)) != _normal_path(str(working_directory)):
        _refuse("DOC04B_ENVIRONMENT_WORKING_DIRECTORY_MISMATCH")
    try:
        forbidden = json.loads(os.environ.get("NEXT_DOC04_FORBIDDEN_ROOTS_JSON", "[]"))
    except json.JSONDecodeError as error:
        raise RuntimeRefusal("DOC04B_FORBIDDEN_ROOTS_INVALID") from error
    if not isinstance(forbidden, list) or any(not isinstance(item, str) for item in forbidden):
        _refuse("DOC04B_FORBIDDEN_ROOTS_INVALID")
    for root in forbidden:
        if root and _is_within(str(working_directory), root):
            _refuse("DOC04B_WORKING_DIRECTORY_FORBIDDEN")
    if policy in NONPRODUCTION_POLICIES and (working_directory / ".env").exists():
        # The positive-control policy intentionally reaches the audit barrier.
        if policy != "nonproduction-audit-probe":
            _refuse(ENV_FORBIDDEN)
    return environment_root, working_directory, policy


def _cwd_sha256(path: pathlib.Path) -> str:
    value = _normal_path(str(path)).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _validate_child_environment(working_directory: pathlib.Path, policy: str) -> None:
    profile = os.environ.get("NEXT_DOC04_RUNTIME_PROFILE", "")
    qualification = {"isolated-test", "isolated-alembic-upgrade"}
    if policy in qualification and profile != "Qualification":
        _refuse("DOC04B_RUNTIME_PROFILE_MISMATCH")
    if policy not in qualification and profile != "Production":
        _refuse("DOC04B_RUNTIME_PROFILE_MISMATCH")
    if policy in PRODUCTION_POLICIES:
        if (
            os.environ.get("POSTGRES_DB") != "ai_lab"
            or os.environ.get("POSTGRES_HOST") != "127.0.0.1"
            or os.environ.get("POSTGRES_PORT") != "5432"
        ):
            _refuse("DOC04B_PRODUCTION_DATABASE_CONTRACT_INVALID")
        return
    if policy == SYNTHETIC_PRODUCTION_POLICY:
        return
    required = {
        "ENVIRONMENT": "test",
        "POSTGRES_USER": "doc04b",
        "POSTGRES_HOST": "127.0.0.1",
        "ADMIN_USERNAME": "synthetic",
        "ADMIN_EMAIL": "synthetic@example.invalid",
    }
    if any(os.environ.get(name) != value for name, value in required.items()):
        _refuse("DOC04B_SYNTHETIC_ENVIRONMENT_INVALID")
    database = os.environ.get("POSTGRES_DB", "")
    if not database.startswith("ai_lab_test_doc04b_"):
        _refuse("DOC04B_ISOLATED_DATABASE_REQUIRED")
    for required_name in (
        "POSTGRES_PASSWORD",
        "POSTGRES_PORT",
        "SECRET_KEY",
        "ADMIN_PASSWORD",
        "N8N_INGEST_API_KEY",
        "DATA_DIR",
    ):
        if not os.environ.get(required_name):
            _refuse("DOC04B_SYNTHETIC_ENVIRONMENT_INVALID")
    if not _is_within(os.environ["DATA_DIR"], str(working_directory)):
        _refuse("DOC04B_SYNTHETIC_DATA_ROOT_INVALID")
    if any(name in os.environ for name in SENSITIVE_ABSENT):
        _refuse("DOC04B_INHERITED_ENVIRONMENT_PRESENT")
    if any("hostile-parent-marker" in value.casefold() for value in os.environ.values()):
        _refuse("DOC04B_INHERITED_ENVIRONMENT_PRESENT")


def _run_git(repo: pathlib.Path, *args: str) -> str:
    executable = os.environ.get("NEXT_DOC04_GIT_EXE", "")
    if not executable or not os.path.isabs(executable) or not os.path.isfile(executable):
        _refuse("DOC04B_GIT_EXECUTABLE_REQUIRED")
    try:
        completed = subprocess.run(
            [executable, "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=30,
        )
    except Exception as error:
        raise RuntimeRefusal("DOC04B_GIT_IDENTITY_FAILED") from error
    return completed.stdout.strip()


def _verify_source() -> pathlib.Path:
    script = pathlib.Path(__file__).resolve()
    repo = script.parents[3]
    expected = os.environ.get("NEXT_DOC04_EXPECTED_GIT_SHA", "")
    if not HEX40.fullmatch(expected):
        _refuse("DOC04B_EXPECTED_GIT_SHA_REQUIRED")
    actual_root = pathlib.Path(_run_git(repo, "rev-parse", "--show-toplevel")).resolve()
    if actual_root != repo or _run_git(repo, "rev-parse", "HEAD") != expected:
        _refuse("DOC04B_GIT_HEAD_MISMATCH")
    lock_path = repo / "operations/windows/doc04-metadata-repair/runtime-lock.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception as error:
        raise RuntimeRefusal("DOC04B_RUNTIME_LOCK_INVALID") from error
    if lock.get("schema") != "NEXT_STABIL_DOC04_WINDOWS_RUNTIME_LOCK_V3":
        _refuse("DOC04B_RUNTIME_LOCK_SCHEMA_MISMATCH")
    for relative in lock["critical_git_paths"]:
        path = repo / pathlib.PurePosixPath(relative)
        if not path.is_file() or _is_reparse_or_link(path):
            _refuse("DOC04B_CRITICAL_SOURCE_INVALID")
        committed = _run_git(repo, "rev-parse", f"HEAD:{relative}")
        working = _run_git(repo, "hash-object", f"--path={relative}", str(path))
        if committed != working:
            _refuse("DOC04B_CRITICAL_SOURCE_MODIFIED")
    return repo


def _import_contract() -> tuple[Any, Any]:
    from app.scripts import repair_document_metadata_surrogates as repair
    from app.services import document_metadata_unicode_safety as safety

    return repair, safety


def _error_code(function: Any) -> str:
    try:
        function()
    except Exception as error:
        return str(getattr(error, "code", type(error).__name__))
    return "NO_ERROR"


def _parser_contract(repair: Any) -> dict[str, Any]:
    parser = repair._parser()
    options = sorted(option for action in parser._actions for option in action.option_strings)
    required = sorted(
        option
        for action in parser._actions
        if action.required
        for option in action.option_strings
    )
    exclusive = sorted(
        sorted(option for action in group._group_actions for option in action.option_strings)
        for group in parser._mutually_exclusive_groups
    )
    help_text = parser.format_help().replace("\r\n", "\n").rstrip() + "\n"
    return {
        "exclusive_groups": exclusive,
        "help_sha256": hashlib.sha256(help_text.encode("utf-8")).hexdigest(),
        "option_names": options,
        "required_options": required,
    }


def _compatibility_vectors() -> dict[str, Any]:
    repair, safety = _import_contract()
    valid_pair = "\ud83d\ude00"
    mixed = "Zażółć\ud800\udc00\ud800\udc00\x00"
    text_inputs = {
        "mixed": mixed,
        "normal_unicode": "Zażółć gęślą jaźń",
        "nul": "a\x00b",
        "unpaired_high": "a\ud800b",
        "unpaired_low": "a\udc00b",
        "valid_surrogate_pair": valid_pair,
    }
    text_vectors = {}
    for name, value in text_inputs.items():
        result = safety.sanitize_metadata_text(value)
        text_vectors[name] = {
            "stats": {
                "preserved_valid_pairs": result.stats.preserved_valid_pairs,
                "replaced_high": result.stats.replaced_high,
                "replaced_low": result.stats.replaced_low,
                "replaced_nul": result.stats.replaced_nul,
            },
            "value": result.value,
        }
    collision = {"\ud800": 1, "\ufffd": 2}
    json_vectors = {
        "collision_error": _error_code(lambda: safety.sanitize_json_compatible(collision)),
        "dynamic_keys": safety.sanitize_json_compatible({7: "seven", "x": 2}),
        "nested": safety.sanitize_json_compatible({"a": ["b\ud800", {"c": 3}]}),
        "non_finite": safety.sanitize_json_compatible([math.nan, math.inf, -math.inf]),
    }
    cycle: list[Any] = []
    cycle.append(cycle)
    assert_vectors = {
        "accepted_safe": _error_code(lambda: safety.assert_json_compatible_safe({"x": [1, "ok"]})),
        "rejected_cycle": _error_code(lambda: safety.assert_json_compatible_safe(cycle)),
        "rejected_non_string_key": _error_code(lambda: safety.assert_json_compatible_safe({1: "x"})),
        "rejected_nul": _error_code(lambda: safety.assert_json_compatible_safe("x\x00")),
        "rejected_unpaired": _error_code(lambda: safety.assert_json_compatible_safe("x\ud800")),
    }
    repair_inputs = {
        "high": '{"v":"a\\uD800b"}',
        "low": '{"v":"a\\uDC00b"}',
        "pair": '{"v":"a\\uD83D\\uDE00b"}',
    }
    repair_vectors = {}
    for name, value in repair_inputs.items():
        repaired = safety.repair_json_text_surrogates(value)
        repair_vectors[name] = repaired.safe_evidence()
    repair_vectors["duplicate_key_error"] = _error_code(
        lambda: safety.repair_json_text_surrogates('{"x":1,"x":2}')
    )
    root = r"X:\Synthetic\Backup\..\Backup\Root"
    contract = {
        "approved_hashes": sorted(
            [
                repair.APPROVED_RAW_BEFORE_SHA256,
                repair.APPROVED_RAW_CANDIDATE_SHA256,
                repair.APPROVED_NORMALIZED_BEFORE_SHA256,
                repair.APPROVED_NORMALIZED_CANDIDATE_SHA256,
            ]
        ),
        "operation_lock_key": repair.OPERATION_LOCK_KEY,
        "target_document_id": repair.TARGET_DOCUMENT_ID,
        "transaction_isolation": repair.REPAIR_TRANSACTION_ISOLATION,
    }
    return {
        "argparse": _parser_contract(repair),
        "assert_json_compatible_safe": assert_vectors,
        "ntpath": {
            "backup_root_sha256": repair._backup_root_sha256(root),
            "normcase": ntpath.normcase(root),
            "normpath": ntpath.normpath(root),
        },
        "repair_contract": contract,
        "repair_json_text_surrogates": repair_vectors,
        "sanitize_json_compatible": json_vectors,
        "sanitize_metadata_text": text_vectors,
    }


def _emit(payload: Any) -> None:
    value = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    os.write(_RESULT_FD, value.encode("utf-8"))


def _bounded_repair_value(value: Any, depth: int = 0) -> None:
    if depth > 8:
        _refuse("DOC04B_REPAIR_RESULT_STRUCTURE_INVALID")
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _refuse("DOC04B_REPAIR_RESULT_STRUCTURE_INVALID")
        return
    if isinstance(value, str):
        if len(value) > 4096 or "\x00" in value:
            _refuse("DOC04B_REPAIR_RESULT_STRUCTURE_INVALID")
        return
    if isinstance(value, list):
        if len(value) > 128:
            _refuse("DOC04B_REPAIR_RESULT_STRUCTURE_INVALID")
        for item in value:
            _bounded_repair_value(item, depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 64:
            _refuse("DOC04B_REPAIR_RESULT_STRUCTURE_INVALID")
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 96 or "\x00" in key:
                _refuse("DOC04B_REPAIR_RESULT_STRUCTURE_INVALID")
            _bounded_repair_value(item, depth + 1)
        return
    _refuse("DOC04B_REPAIR_RESULT_STRUCTURE_INVALID")


def _validate_repair_payload(payload: Any, exit_code: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        _refuse("DOC04B_REPAIR_RESULT_NOT_OBJECT")
    allowed_keys = {
        "affected_columns",
        "affected_documents",
        "backup_manifest_sha256",
        "backup_run_id",
        "database",
        "document_id",
        "executed",
        "metadata_normalized",
        "metadata_raw",
        "production_preflight",
        "result",
    }
    if set(payload) - allowed_keys:
        _refuse("DOC04B_REPAIR_RESULT_KEYS_INVALID")
    _bounded_repair_value(payload)
    result = payload.get("result")
    executed = payload.get("executed")
    if not isinstance(result, str) or not REPAIR_RESULT.fullmatch(result):
        _refuse("DOC04B_REPAIR_RESULT_CODE_INVALID")
    if not isinstance(executed, bool):
        _refuse("DOC04B_REPAIR_RESULT_EXECUTED_INVALID")
    if not isinstance(exit_code, int) or not 0 <= exit_code <= 255:
        _refuse("DOC04B_REPAIR_EXIT_CODE_INVALID")
    if exit_code == 0:
        if result not in REPAIR_SUCCESS_CODES:
            _refuse("DOC04B_REPAIR_SUCCESS_REFUSAL_CONTRADICTION")
        if executed != (result == "DOCUMENT_METADATA_REPAIR_EXECUTED"):
            _refuse("DOC04B_REPAIR_SUCCESS_EXECUTED_CONTRADICTION")
    elif executed or result in REPAIR_SUCCESS_CODES:
        _refuse("DOC04B_REPAIR_FAILURE_EXECUTED_CONTRADICTION")
    return payload


def _invoke_and_relay_repair(
    repair_args: list[str], repair_callable: Any | None = None
) -> int:
    if repair_callable is None:
        from app.scripts.repair_document_metadata_surrogates import (
            main as repair_main,
        )

        repair_callable = repair_main
    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(
        captured_stderr
    ):
        exit_code = int(repair_callable(repair_args))
    stdout = captured_stdout.getvalue()
    stderr = captured_stderr.getvalue()
    if stderr:
        _refuse("DOC04B_REPAIR_STDERR_NOT_EMPTY")
    encoded = stdout.encode("utf-8", errors="strict")
    if len(encoded) > MAX_REPAIR_OUTPUT_BYTES:
        _refuse("DOC04B_REPAIR_OUTPUT_OVERSIZED")
    if b"\x00" in encoded:
        _refuse("DOC04B_REPAIR_OUTPUT_NUL")
    lines = stdout.splitlines()
    if len(lines) != 1 or not lines[0].strip():
        _refuse("DOC04B_REPAIR_OUTPUT_LINE_COUNT_INVALID")
    try:
        payload = json.loads(lines[0])
    except json.JSONDecodeError as error:
        raise RuntimeRefusal("DOC04B_REPAIR_OUTPUT_JSON_INVALID") from error
    payload = _validate_repair_payload(payload, exit_code)
    _emit(payload)
    return exit_code


def _relay_self_test(case: str) -> int:
    def fixed(_: list[str]) -> int:
        if case == "success":
            print('{"executed":false,"result":"DOCUMENT_METADATA_REPAIR_DRY_RUN"}')
            return 0
        if case == "refusal":
            print('{"executed":false,"result":"DOCUMENT_METADATA_REPAIR_REFUSED"}')
            return 2
        if case == "empty":
            return 2
        if case == "multiple":
            print('{"executed":false,"result":"DOCUMENT_METADATA_REPAIR_REFUSED"}')
            print('{"executed":false,"result":"DOCUMENT_METADATA_REPAIR_REFUSED"}')
            return 2
        if case == "invalidjson":
            print("not-json")
            return 2
        if case == "oversized":
            print('{"executed":false,"result":"DOCUMENT_METADATA_REPAIR_REFUSED","database":"' + ("x" * 66_000) + '"}')
            return 2
        if case == "nul":
            print('{"executed":false,"result":"DOCUMENT_METADATA_REPAIR_REFUSED"}\x00')
            return 2
        if case == "stderr":
            print('{"executed":false,"result":"DOCUMENT_METADATA_REPAIR_REFUSED"}')
            print("bounded-test-stderr", file=sys.stderr)
            return 2
        if case == "contradictory":
            print('{"executed":false,"result":"DOCUMENT_METADATA_REPAIR_REFUSED"}')
            return 0
        _refuse("DOC04B_RELAY_SELF_TEST_CASE_INVALID")
        return 2

    return _invoke_and_relay_repair([], fixed)


def _normalize_distribution(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).casefold()


def _production_import_trace() -> dict[str, Any]:
    before = set(sys.modules)
    _import_contract()
    import psycopg

    if psycopg.pq.__impl__ != "binary":
        _refuse("DOC04B_PSYCOPG_BINARY_NOT_ACTIVE")
    loaded_roots = {name.split(".", 1)[0] for name in set(sys.modules) - before}
    package_map = importlib.metadata.packages_distributions()
    loaded_distributions = {
        distribution
        for root in loaded_roots
        for distribution in package_map.get(root, ())
    }
    expected = {_normalize_distribution(name) for name in PRODUCTION_EXPECTED_PACKAGES}
    observed = {
        _normalize_distribution(name)
        for name in loaded_distributions
        if _normalize_distribution(name) in expected
    }
    if observed != expected:
        _refuse("DOC04B_PRODUCTION_IMPORT_CLOSURE_MISMATCH")
    return {
        "distributions": sorted(PRODUCTION_EXPECTED_PACKAGES),
        "package_count": len(PRODUCTION_EXPECTED_PACKAGES),
        "psycopg_implementation": psycopg.pq.__impl__,
        "result": "DOC04B_PRODUCTION_IMPORT_TRACE_PASS",
    }


def _assert_database_isolated() -> None:
    database = os.environ.get("POSTGRES_DB", "")
    host = os.environ.get("POSTGRES_HOST", "")
    port = os.environ.get("POSTGRES_PORT", "")
    if not database.startswith("ai_lab_test_doc04b_") or host != "127.0.0.1" or port == "5432":
        _refuse("DOC04B_ISOLATED_DATABASE_REQUIRED")


def _smoke(working_directory: pathlib.Path) -> dict[str, Any]:
    repair, _ = _import_contract()
    versions = {
        name: importlib.metadata.version(name)
        for name in PRODUCTION_EXPECTED_PACKAGES
    }
    if versions != PRODUCTION_EXPECTED_PACKAGES:
        _refuse("DOC04B_PACKAGE_VERSION_MISMATCH")
    if repair.OPERATION_LOCK_KEY != 0x4E455854424B5253:
        _refuse("DOC04B_OPERATION_LOCK_KEY_MISMATCH")
    if not repair._parser().format_help():
        _refuse("DOC04B_REPAIR_HELP_INVALID")
    return {
        "architecture": "amd64" if sys.maxsize > 2**32 else "x86",
        "cwd_identity_sha256": _cwd_sha256(working_directory),
        "database_connections": 0,
        "environment_profile": "synthetic_explicit",
        "env_file_open_attempts": _ENV_FILE_OPEN_ATTEMPTS,
        "network_connections": 0,
        "packages": versions,
        "python": platform.python_version(),
        "result": "DOC04B_SMOKE_PASS",
    }


def _iter_tests(suite: unittest.TestSuite) -> Iterator[unittest.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def _run_tests(suite_name: str) -> dict[str, Any]:
    global _SAFE_FAILURE_DETAILS
    _assert_database_isolated()
    if suite_name == "intake":
        captured = io.StringIO()
        try:
            module = importlib.import_module(FIXED_TEST_SUITES[suite_name][0])
            with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                module.main()
        except Exception as error:
            category = re.sub(
                r"[^A-Z0-9_]", "_", type(error).__name__.upper()
            )[:80]
            _refuse("DOC04B_INTAKE_CONTRACT_FAILED_" + category)
        return {
            "errors": 0,
            "failures": 0,
            "prefix_counts": {key: 0 for key in ("U", "R", "G", "H", "I")},
            "result": "DOC04B_ISOLATED_TEST_PASS",
            "skipped": 0,
            "suite": suite_name,
            "tests_run": 1,
        }
    modules = FIXED_TEST_SUITES[suite_name]
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    test_names = [getattr(test, "_testMethodName", "") for test in _iter_tests(suite)]
    prefix_counts = {
        prefix.upper(): sum(name.lower().startswith(f"test_{prefix}") for name in test_names)
        for prefix in ("u", "r", "g", "h", "i")
    }
    captured = io.StringIO()
    result = unittest.TextTestRunner(stream=captured, verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped:
        failed = []
        for test, _ in list(result.failures) + list(result.errors):
            method = getattr(test, "_testMethodName", None)
            if not method:
                method = re.sub(r"[^A-Za-z0-9_.-]", "_", str(test))[:160]
            failed.append(method or "unknown")
        error_types = []
        missing_modules = []
        for _, traceback_text in list(result.failures) + list(result.errors):
            lines = [line.strip() for line in traceback_text.splitlines() if line.strip()]
            categories = []
            for line in lines:
                match = re.match(
                    r"^(?:[A-Za-z_][A-Za-z0-9_]*\.)*"
                    r"([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))\s*:",
                    line,
                )
                if match:
                    categories.append(match.group(1))
            error_types.extend(
                re.sub(r"[^A-Z0-9_]", "_", category.upper())[:80]
                for category in (categories or ["UNKNOWN"])
            )
            missing = re.findall(r"No module named ['\"]([A-Za-z0-9_.-]+)['\"]", traceback_text)
            missing_modules.extend(re.sub(r"[^A-Z0-9_]", "_", item.upper())[:80] for item in missing)
        _SAFE_FAILURE_DETAILS = {
            "error_count": len(result.errors),
            "error_types": sorted(set(error_types))[:8],
            "failure_count": len(result.failures),
            "failure_methods": sorted(set(failed))[:16],
            "missing_modules": sorted(set(missing_modules))[:8],
            "skipped_count": len(result.skipped),
            "tests_run": result.testsRun,
        }
        method_suffix = "_".join(
            re.sub(r"[^A-Z0-9_]", "_", method.upper())[:160]
            for method in _SAFE_FAILURE_DETAILS["failure_methods"]
        )
        type_suffix = "_".join(_SAFE_FAILURE_DETAILS["error_types"])
        missing_suffix = "_".join(_SAFE_FAILURE_DETAILS["missing_modules"])
        if method_suffix:
            _refuse(
                "DOC04B_ISOLATED_TEST_FAILED_"
                + method_suffix
                + "_"
                + type_suffix
                + ("_MISSING_" + missing_suffix if missing_suffix else "")
            )
        _refuse(
            "DOC04B_ISOLATED_TEST_FAILED_"
            f"F{len(result.failures)}_E{len(result.errors)}_S{len(result.skipped)}"
        )
    return {
        "errors": len(result.errors),
        "failures": len(result.failures),
        "prefix_counts": prefix_counts,
        "result": "DOC04B_ISOLATED_TEST_PASS",
        "skipped": len(result.skipped),
        "suite": suite_name,
        "tests_run": result.testsRun,
    }


def _run_alembic(repo: pathlib.Path) -> dict[str, Any]:
    _assert_database_isolated()
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from app.core.config import settings

    engine = create_engine(settings.database_url, future=True)
    try:
        with engine.connect() as connection:
            actual = connection.execute(text("SELECT current_database()"))
            if actual.scalar_one() != settings.postgres_db:
                _refuse("DOC04B_DATABASE_IDENTITY_MISMATCH")
    finally:
        engine.dispose()
    config = Config(str(repo / "backend/alembic.ini"))
    config.set_main_option("script_location", str(repo / "backend/alembic"))
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        command.upgrade(config, ISOLATED_DATABASE_REVISION)
    verification = create_engine(settings.database_url, future=True)
    try:
        with verification.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            if revision != ISOLATED_DATABASE_REVISION:
                _refuse("DOC04B_ALEMBIC_REVISION_MISMATCH")
    finally:
        verification.dispose()
    return {
        "database_prefix": "ai_lab_test_doc04b_",
        "revision": ISOLATED_DATABASE_REVISION,
        "result": "DOC04B_ALEMBIC_UPGRADE_PASS",
    }


def _repair_help() -> dict[str, Any]:
    repair, _ = _import_contract()
    parser = _parser_contract(repair)
    return {
        "database_connections": 0,
        "env_file_open_attempts": _ENV_FILE_OPEN_ATTEMPTS,
        "help_sha256": parser["help_sha256"],
        "network_connections": 0,
        "option_count": len(parser["option_names"]),
        "result": "DOC04B_REPAIR_HELP_PASS",
    }


def _synthetic_production_audit(working_directory: pathlib.Path) -> dict[str, Any]:
    allowed = working_directory / ".env"
    rejected = working_directory / "second" / ".env"
    with allowed.open("rb") as handle:
        if not handle.read(1):
            _refuse("DOC04B_SYNTHETIC_ENV_CONTROL_INVALID")
    rejected_code = "NO_ERROR"
    try:
        with rejected.open("rb"):
            pass
    except RuntimeRefusal as error:
        rejected_code = str(error)
    if rejected_code != ENV_FORBIDDEN:
        _refuse("DOC04B_PRODUCTION_ENV_ALLOWLIST_INVALID")
    return {
        "allowed_env_opens": 1,
        "env_file_open_attempts": _ENV_FILE_OPEN_ATTEMPTS,
        "rejected_env_opens": 1,
        "result": "DOC04B_SYNTHETIC_PRODUCTION_ENV_AUDIT_PASS",
    }


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("smoke", add_help=False)
    sub.add_parser("compatibility-vectors", add_help=False)
    sub.add_parser("production-import-trace", add_help=False)
    relay = sub.add_parser("repair-relay-self-test", add_help=False)
    relay.add_argument(
        "--case",
        choices=(
            "success",
            "refusal",
            "empty",
            "multiple",
            "invalidjson",
            "oversized",
            "nul",
            "stderr",
            "contradictory",
        ),
        required=True,
    )
    repair = sub.add_parser("repair", add_help=False)
    repair.add_argument("repair_args", nargs=argparse.REMAINDER)
    tests = sub.add_parser("isolated-test", add_help=False)
    tests.add_argument("--suite", choices=sorted(FIXED_TEST_SUITES), required=True)
    sub.add_parser("isolated-alembic-upgrade", add_help=False)
    sub.add_parser("synthetic-production-audit", add_help=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] == "repair":
        args = argparse.Namespace(mode="repair", repair_args=raw_args[1:])
    else:
        args = _argument_parser().parse_args(raw_args)
    environment_root, working_directory, policy = _environment_roots()
    if policy in PRODUCTION_POLICIES | {SYNTHETIC_PRODUCTION_POLICY}:
        expected_env_file = environment_root / ".env"
        configured_env_file = os.environ.get("NEXT_DOC04_ALLOWED_ENV_FILE", "")
        if (
            not configured_env_file
            or _normal_path(configured_env_file) != _normal_path(str(expected_env_file))
        ):
            _refuse("DOC04B_PRODUCTION_ENV_ALLOWLIST_INVALID")
        _assert_regular_non_reparse_file(
            expected_env_file, "DOC04B_PRODUCTION_ENV_FILE_INVALID"
        )
        allowed_env_file = str(expected_env_file)
    else:
        allowed_env_file = None
    _install_env_audit_guard(allowed_env_file)
    os.chdir(working_directory)
    if _normal_path(os.getcwd()) != _normal_path(str(working_directory)):
        _refuse("DOC04B_WORKING_DIRECTORY_NOT_APPLIED")
    _validate_child_environment(working_directory, policy)
    null_fd = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(null_fd, 1)
        os.dup2(null_fd, 2)
    finally:
        os.close(null_fd)

    if args.mode == "synthetic-production-audit":
        if policy != SYNTHETIC_PRODUCTION_POLICY:
            _refuse("DOC04B_RUNTIME_POLICY_MODE_MISMATCH")
        _emit(_synthetic_production_audit(working_directory))
        return 0

    backend_reference = policy == "backend-reference"
    if backend_reference:
        if (
            args.mode != "compatibility-vectors"
            or os.name == "nt"
            or platform.python_version() != "3.12.13"
            or os.environ.get("NEXT_DOC04_BACKEND_REFERENCE") != "1"
        ):
            _refuse("DOC04B_BACKEND_REFERENCE_MODE_INVALID")
        repo = pathlib.Path("/app")
        sys.path.insert(0, "/app")
    else:
        repo = _verify_source()
        sys.path.insert(0, str(repo / "backend"))
    sys.dont_write_bytecode = True

    expected_policy = {
        "smoke": {"readiness", "nonproduction-audit-probe"},
        "compatibility-vectors": {"compatibility-vectors", "backend-reference"},
        "production-import-trace": {"production-import-trace"},
        "repair-relay-self-test": {"repair-relay-self-test"},
        "isolated-test": {"isolated-test"},
        "isolated-alembic-upgrade": {"isolated-alembic-upgrade"},
        "repair": {"repair-help", "production-preflight", "production-execute"},
    }[args.mode]
    if policy not in expected_policy:
        _refuse("DOC04B_RUNTIME_POLICY_MODE_MISMATCH")

    if args.mode == "compatibility-vectors":
        _emit(_compatibility_vectors())
        return 0
    if args.mode == "production-import-trace":
        _emit(_production_import_trace())
        return 0
    if args.mode == "repair-relay-self-test":
        return _relay_self_test(args.case)
    if args.mode == "smoke":
        _emit(_smoke(working_directory))
        return 0
    if args.mode == "isolated-test":
        _emit(_run_tests(args.suite))
        return 0
    if args.mode == "isolated-alembic-upgrade":
        _emit(_run_alembic(repo))
        return 0
    if args.mode == "repair" and policy == "repair-help":
        if args.repair_args not in (["--help"], ["-h"]):
            _refuse("DOC04B_REPAIR_HELP_ONLY")
        _emit(_repair_help())
        return 0
    if args.mode == "repair":
        return _invoke_and_relay_repair(args.repair_args)
    _refuse()
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeRefusal as error:
        code = str(error)
        payload = {"env_file_open_attempts": _ENV_FILE_OPEN_ATTEMPTS, "result": code}
        payload.update(_SAFE_FAILURE_DETAILS)
        os.write(_ERROR_FD, (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
        raise SystemExit(2)
    except Exception:
        code = ENV_FORBIDDEN if _ENV_FILE_OPEN_ATTEMPTS else "DOC04B_RUNTIME_UNEXPECTED_FAILURE"
        payload = {"env_file_open_attempts": _ENV_FILE_OPEN_ATTEMPTS, "result": code}
        os.write(_ERROR_FD, (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
        raise SystemExit(2)
