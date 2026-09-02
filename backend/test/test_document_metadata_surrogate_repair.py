from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError

from app.database.session import SessionLocal, engine
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.scripts import repair_document_metadata_surrogates as repair_module
from app.scripts.repair_document_metadata_surrogates import (
    APPROVED_NORMALIZED_BEFORE_SHA256,
    APPROVED_NORMALIZED_CANDIDATE_SHA256,
    APPROVED_RAW_BEFORE_SHA256,
    APPROVED_RAW_CANDIDATE_SHA256,
    REPAIR_ACTIVE_OPERATION,
    REPAIR_ALEMBIC_MISMATCH,
    REPAIR_BACKUP_DISAPPEARED,
    REPAIR_BACKUP_INVALID,
    REPAIR_BACKUP_MANIFEST_MISMATCH,
    REPAIR_BACKUP_PATH_INVALID,
    REPAIR_BACKUP_SCOPE_INVALID,
    REPAIR_BACKUP_STALE,
    REPAIR_BACKUP_TIME_MISMATCH,
    REPAIR_BEFORE_HASH,
    REPAIR_CANDIDATE_HASH,
    REPAIR_CONCURRENCY,
    REPAIR_OPERATION_LOCK_BUSY,
    REPAIR_POSTCONDITION,
    REPAIR_PRODUCTION_GUARD,
    REPAIR_RUNTIME_SOURCE_MISMATCH,
    REPAIR_SCOPE,
    REPAIR_STORAGE,
    REPAIR_TARGET_MISSING,
    REPAIR_TARGET_ACTIVE,
    REPAIR_TRANSACTION_ISOLATION,
    BackupEvidence,
    DocumentMetadataRepairError,
    RepairContract,
    RepairResult,
    _assert_no_active_operations,
    _assert_target_quiescent,
    _acquire_backup_restore_operation_lock,
    _backup_root_sha256,
    _parser,
    _revalidate_production_guards,
    _validate_backup_evidence,
    _validate_production_gate,
    _verify_backup_physical,
    _verify_runtime_source_identity,
    execute_repair,
)
from app.services.backup_restore_service import OPERATION_LOCK_KEY
from app.services.document_metadata_unicode_safety import (
    DOCUMENT_METADATA_JSON_INVALID,
    DOCUMENT_METADATA_UNICODE_KEY_COLLISION,
    DocumentMetadataSafetyError,
    assert_json_compatible_safe,
    repair_json_text_surrogates,
    sanitize_json_compatible,
    sanitize_metadata_text,
)
from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()
EXPECTED_HEAD = "followup_assistant_chat_history_20260829"
TARGET_ID = 8903
OTHER_ID = 8904
RAW_FIXTURE = (
    r'{"note": "synthetic-low-\uDC00", "number": 1.00}'
)
NORMALIZED_FIXTURE = (
    r'{"items":["synthetic-high-\uD800"],"flag":true}'
)
SAFE_FIXTURE = r'{"safe":"synthetic-safe","number":2.00}'
FILE_CONTENT = b"synthetic-doc04a-storage"
UPDATED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
OPERATION_FIXTURE_ROLE = "DOC04A3Role"
OPERATION_FIXTURE_USER = "doc04a3-actor"


class _ScalarResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one(self) -> object:
        return self.value


def _sha256(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _backup_evidence(
    root: Path,
    *,
    scope: str = "database",
    **changes: object,
) -> BackupEvidence:
    checkpoint = root / "checkpoint"
    manifest = checkpoint / "manifest.json"
    values: dict[str, object] = {
        "backup_run_id": 7001,
        "run_scope": scope,
        "status": "completed",
        "stage": "completed",
        "verified": True,
        "schedule_id": 17,
        "started_at": UPDATED_AT - timedelta(minutes=10),
        "finished_at": UPDATED_AT,
        "managed_backup_run_id": 7001,
        "managed_scope": scope,
        "integrity_status": "verified",
        "lifecycle": "available",
        "deleted_at": None,
        "destination_root": str(root),
        "checkpoint_path": str(checkpoint),
        "manifest_path": str(manifest),
        "manifest_sha256": (
            _sha256(manifest.read_bytes())
            if manifest.is_file()
            else "a" * 64
        ),
        "source_head": "c" * 40,
        "db_revision": EXPECTED_HEAD,
        "managed_created_at": UPDATED_AT,
    }
    values.update(changes)
    return BackupEvidence(**values)


def _guard_contract(
    evidence: BackupEvidence | None = None,
    **changes: object,
) -> RepairContract:
    contract = RepairContract(
        expected_database="ai_lab",
        expected_alembic_head=EXPECTED_HEAD,
        expected_xmin="1",
        expected_updated_at=UPDATED_AT,
        expected_storage_sha256="b" * 64,
        expected_raw_before_sha256=APPROVED_RAW_BEFORE_SHA256,
        expected_raw_candidate_sha256=APPROVED_RAW_CANDIDATE_SHA256,
        expected_normalized_before_sha256=(
            APPROVED_NORMALIZED_BEFORE_SHA256
        ),
        expected_normalized_candidate_sha256=(
            APPROVED_NORMALIZED_CANDIDATE_SHA256
        ),
        expected_git_sha="c" * 40,
        allow_production_ai_lab=True,
        owner_approval_id="synthetic-approval",
        verified_backup_run_id=(
            evidence.backup_run_id if evidence else 7001
        ),
        verified_backup_manifest_sha256=(
            evidence.manifest_sha256 if evidence else "a" * 64
        ),
        expected_backup_finished_at=(
            evidence.finished_at if evidence else UPDATED_AT
        ),
        maximum_backup_age_seconds=3600,
        expected_backup_destination_root_sha256=(
            _backup_root_sha256(evidence.destination_root)
            if evidence
            else "d" * 64
        ),
    )
    return replace(contract, **changes)


class DocumentMetadataLexicalRepairTests(unittest.TestCase):
    def test_r01_lexical_isolated_low_replacement(self) -> None:
        result = repair_json_text_surrogates(r'{"x":"a\uDC00b"}')
        self.assertEqual(result.candidate_text, r'{"x":"a\uFFFDb"}')
        self.assertEqual(result.replaced_low, 1)

    def test_r02_lexical_isolated_high_replacement(self) -> None:
        result = repair_json_text_surrogates(r'{"x":"a\uD800b"}')
        self.assertEqual(result.candidate_text, r'{"x":"a\uFFFDb"}')
        self.assertEqual(result.replaced_high, 1)

    def test_r03_adjacent_invalid_low_escapes(self) -> None:
        result = repair_json_text_surrogates(
            r'{"x":"\uDC00\uDFFF"}'
        )
        self.assertEqual(
            result.candidate_text,
            r'{"x":"\uFFFD\uFFFD"}',
        )
        self.assertEqual(result.replaced_low, 2)

    def test_r04_valid_surrogate_escape_pair_preserved(self) -> None:
        source = r'{"x":"\uD83D\uDE00"}'
        result = repair_json_text_surrogates(source)
        self.assertEqual(result.candidate_text, source)
        self.assertEqual(result.preserved_valid_pairs, 1)
        self.assertEqual(result.replacement_count, 0)

    def test_r05_escaped_literal_backslash_u_untouched(self) -> None:
        source = r'{"x":"\\uD800"}'
        result = repair_json_text_surrogates(source)
        self.assertEqual(result.candidate_text, source)
        self.assertEqual(result.replacement_count, 0)

    def test_r06_escaped_quote_boundary(self) -> None:
        source = r'{"quote":"escaped \" marker","bad":"\uDC00"}'
        result = repair_json_text_surrogates(source)
        self.assertEqual(
            result.candidate_text,
            r'{"quote":"escaped \" marker","bad":"\uFFFD"}',
        )

    def test_r07_mixed_hexadecimal_case(self) -> None:
        result = repair_json_text_surrogates(r'{"x":"\uDcAf"}')
        self.assertEqual(result.candidate_text, r'{"x":"\uFFFD"}')
        self.assertEqual(result.replaced_low, 1)

    def test_r08_unicode_like_text_outside_string_refused(self) -> None:
        with self.assertRaises(DocumentMetadataSafetyError) as raised:
            repair_json_text_surrogates(r'{"x":1}\uDC00')
        self.assertEqual(
            raised.exception.code,
            DOCUMENT_METADATA_JSON_INVALID,
        )

    def test_r09_lexical_form_is_byte_identical_except_escape(self) -> None:
        source = (
            '{\n  "z" : 1.00, "a": [true, "x\\uDC00"], '
            '"n": 1e+03\n}'
        )
        result = repair_json_text_surrogates(source)
        expected = source.replace(r"\uDC00", r"\uFFFD")
        self.assertEqual(result.candidate_text, expected)
        self.assertEqual(len(result.candidate_text), len(source))

    def test_r10_duplicate_keys_are_rejected(self) -> None:
        with self.assertRaises(DocumentMetadataSafetyError) as raised:
            repair_json_text_surrogates('{"a":1,"a":2}')
        self.assertEqual(
            raised.exception.code,
            DOCUMENT_METADATA_UNICODE_KEY_COLLISION,
        )

    def test_r11_paths_and_cardinalities_preserved(self) -> None:
        source = r'{"a":[{"b":"\uDC00"},2],"c":{"d":3}}'
        result = repair_json_text_surrogates(
            source
        )
        self.assertEqual(result.top_level_type, "object")
        before = json.loads(source)
        after = json.loads(result.candidate_text)
        self.assertEqual(set(before), set(after))
        self.assertEqual(len(before["a"]), len(after["a"]))
        self.assertEqual(set(before["a"][0]), set(after["a"][0]))
        self.assertEqual(set(before["c"]), set(after["c"]))

    def test_r12_safe_evidence_contains_no_value_text(self) -> None:
        marker = "synthetic-private-marker"
        result = repair_json_text_surrogates(
            '{"x":"' + marker + r'-\uDC00"}'
        )
        evidence = result.safe_evidence()
        encoded = json.dumps(evidence, sort_keys=True)
        self.assertNotIn(marker, encoded)
        self.assertNotIn("candidate_text", evidence)
        self.assertIn("before_sha256", evidence)
        self.assertIn("replacements", evidence)


class DocumentMetadataProductionGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "backup"
        self.checkpoint = self.root / "checkpoint"
        self.checkpoint.mkdir(parents=True)
        self.manifest = self.checkpoint / "manifest.json"
        self.manifest.write_bytes(b'{"synthetic":"manifest"}')

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _evidence(self, **changes: object) -> BackupEvidence:
        return _backup_evidence(self.root, **changes)

    def _contract(
        self,
        evidence: BackupEvidence | None = None,
        **changes: object,
    ) -> RepairContract:
        return _guard_contract(evidence or self._evidence(), **changes)

    def _validate(
        self,
        evidence: BackupEvidence,
        *,
        contract: RepairContract | None = None,
        now: datetime | None = None,
    ) -> None:
        _validate_backup_evidence(
            evidence,
            contract=contract or self._contract(evidence),
            transaction_time=now or UPDATED_AT + timedelta(minutes=5),
        )

    def _expect(
        self,
        code: str,
        evidence: BackupEvidence,
        *,
        contract: RepairContract | None = None,
        now: datetime | None = None,
    ) -> None:
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            self._validate(
                evidence,
                contract=contract,
                now=now,
            )
        self.assertEqual(raised.exception.code, code)

    def test_g01_database_backup_passes(self) -> None:
        evidence = self._evidence(scope="database")
        self._validate(evidence)

    def test_g02_full_backup_passes(self) -> None:
        evidence = self._evidence(scope="full")
        self._validate(evidence)

    def test_g03_n8n_config_backup_rejected(self) -> None:
        evidence = self._evidence(scope="n8n_config")
        self._expect(REPAIR_BACKUP_SCOPE_INVALID, evidence)

    def test_g04_documents_backup_rejected(self) -> None:
        evidence = self._evidence(scope="documents")
        self._expect(REPAIR_BACKUP_SCOPE_INVALID, evidence)

    def test_g05_qdrant_backup_rejected(self) -> None:
        evidence = self._evidence(scope="qdrant")
        self._expect(REPAIR_BACKUP_SCOPE_INVALID, evidence)

    def test_g06_backup_scope_mismatch_rejected(self) -> None:
        evidence = self._evidence(managed_scope="full")
        self._expect(REPAIR_BACKUP_SCOPE_INVALID, evidence)

    def test_g07_db_revision_mismatch_rejected(self) -> None:
        evidence = self._evidence(db_revision="synthetic-wrong")
        self._expect(REPAIR_BACKUP_INVALID, evidence)

    def test_g08_source_head_mismatch_rejected(self) -> None:
        evidence = self._evidence(source_head="e" * 40)
        self._expect(REPAIR_BACKUP_INVALID, evidence)

    def test_g09_finished_at_mismatch_rejected(self) -> None:
        evidence = self._evidence()
        contract = self._contract(
            evidence,
            expected_backup_finished_at=UPDATED_AT - timedelta(seconds=1),
        )
        self._expect(
            REPAIR_BACKUP_TIME_MISMATCH,
            evidence,
            contract=contract,
        )

    def test_g10_stale_backup_rejected(self) -> None:
        evidence = self._evidence()
        contract = self._contract(
            evidence,
            maximum_backup_age_seconds=60,
        )
        self._expect(
            REPAIR_BACKUP_STALE,
            evidence,
            contract=contract,
            now=UPDATED_AT + timedelta(seconds=61),
        )
        for invalid_maximum in (0, 86_401):
            with self.subTest(invalid_maximum=invalid_maximum):
                self._expect(
                    REPAIR_BACKUP_STALE,
                    evidence,
                    contract=self._contract(
                        evidence,
                        maximum_backup_age_seconds=invalid_maximum,
                    ),
                    now=UPDATED_AT + timedelta(seconds=1),
                )

    def test_g11_future_backup_rejected(self) -> None:
        evidence = self._evidence()
        for transaction_time in (
            UPDATED_AT,
            UPDATED_AT - timedelta(microseconds=1),
        ):
            with self.subTest(transaction_time=transaction_time):
                self._expect(
                    REPAIR_BACKUP_STALE,
                    evidence,
                    now=transaction_time,
                )

    def test_g12_unavailable_deleted_unverified_rejected(self) -> None:
        variants = (
            {"lifecycle": "deleted"},
            {"deleted_at": UPDATED_AT},
            {"verified": False},
            {"integrity_status": "unverified"},
            {"status": "failed"},
            {"stage": "failed"},
        )
        for changes in variants:
            with self.subTest(changes=changes):
                evidence = self._evidence(**changes)
                self._expect(REPAIR_BACKUP_INVALID, evidence)

    def test_g13_missing_destination_root_rejected(self) -> None:
        missing = Path(self.temporary.name) / "missing-root"
        evidence = self._evidence(destination_root=str(missing))
        contract = self._contract(
            evidence,
            expected_backup_destination_root_sha256=(
                _backup_root_sha256(str(missing))
            ),
        )
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _verify_backup_physical(
                evidence,
                contract=contract,
                recheck=False,
            )
        self.assertEqual(raised.exception.code, REPAIR_BACKUP_PATH_INVALID)

    def test_g14_checkpoint_outside_root_rejected(self) -> None:
        outside = Path(self.temporary.name) / "outside-checkpoint"
        outside.mkdir()
        evidence = self._evidence(checkpoint_path=str(outside))
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _verify_backup_physical(
                evidence,
                contract=self._contract(evidence),
                recheck=False,
            )
        self.assertEqual(raised.exception.code, REPAIR_BACKUP_PATH_INVALID)
        if os.name != "nt":
            linked = self.root / "linked-checkpoint"
            linked.symlink_to(self.checkpoint, target_is_directory=True)
            evidence = self._evidence(checkpoint_path=str(linked))
            with self.assertRaises(DocumentMetadataRepairError) as raised:
                _verify_backup_physical(
                    evidence,
                    contract=self._contract(evidence),
                    recheck=False,
                )
            self.assertEqual(
                raised.exception.code,
                REPAIR_BACKUP_PATH_INVALID,
            )

    def test_g15_manifest_outside_root_rejected(self) -> None:
        outside = Path(self.temporary.name) / "outside-manifest.json"
        outside.write_bytes(self.manifest.read_bytes())
        evidence = self._evidence(manifest_path=str(outside))
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _verify_backup_physical(
                evidence,
                contract=self._contract(evidence),
                recheck=False,
            )
        self.assertEqual(raised.exception.code, REPAIR_BACKUP_PATH_INVALID)

    def test_g16_missing_checkpoint_rejected(self) -> None:
        missing = self.root / "missing-checkpoint"
        evidence = self._evidence(checkpoint_path=str(missing))
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _verify_backup_physical(
                evidence,
                contract=self._contract(evidence),
                recheck=False,
            )
        self.assertEqual(raised.exception.code, REPAIR_BACKUP_PATH_INVALID)

    def test_g17_missing_manifest_rejected(self) -> None:
        missing = self.checkpoint / "missing-manifest.json"
        evidence = self._evidence(manifest_path=str(missing))
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _verify_backup_physical(
                evidence,
                contract=self._contract(evidence),
                recheck=False,
            )
        self.assertEqual(raised.exception.code, REPAIR_BACKUP_PATH_INVALID)

    def test_g18_manifest_hash_mismatch_rejected(self) -> None:
        evidence = self._evidence(manifest_sha256="0" * 64)
        contract = self._contract(
            evidence,
            verified_backup_manifest_sha256="0" * 64,
        )
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _verify_backup_physical(
                evidence,
                contract=contract,
                recheck=False,
            )
        self.assertEqual(
            raised.exception.code,
            REPAIR_BACKUP_MANIFEST_MISMATCH,
        )

    def test_g19_lifecycle_change_before_commit_rejected(self) -> None:
        initial = self._evidence()
        changed = replace(initial, lifecycle="deleting")
        connection = MagicMock()
        connection.execute.return_value = _ScalarResult(
            UPDATED_AT + timedelta(minutes=5)
        )
        with (
            patch.object(repair_module, "_assert_no_active_operations"),
            patch.object(repair_module, "_assert_target_quiescent"),
            patch.object(repair_module, "_reload_target_state", return_value={}),
            patch.object(repair_module, "_verify_runtime_source_identity"),
            patch.object(repair_module, "_load_backup_evidence", return_value=changed),
        ):
            with self.assertRaises(DocumentMetadataRepairError) as raised:
                _revalidate_production_guards(
                    connection,
                    contract=self._contract(initial),
                    initial_backup=initial,
                )
        self.assertEqual(raised.exception.code, REPAIR_BACKUP_INVALID)

    def test_g20_manifest_disappears_before_commit(self) -> None:
        evidence = self._evidence()
        contract = self._contract(evidence)
        _verify_backup_physical(
            evidence,
            contract=contract,
            recheck=False,
        )
        self.manifest.unlink()
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _verify_backup_physical(
                evidence,
                contract=contract,
                recheck=True,
            )
        self.assertEqual(raised.exception.code, REPAIR_BACKUP_DISAPPEARED)

    def _git_repository(self) -> tuple[Path, Path, str]:
        if shutil.which("git") is None:
            self.skipTest(
                "git executable unavailable in the backend runtime image"
            )
        repository = Path(self.temporary.name) / "identity-repository"
        for relative in repair_module._CRITICAL_RUNTIME_PATHS:
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("synthetic:" + relative + "\n").encode())
        subprocess.run(
            ["git", "init"], cwd=repository, check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "doc04a@test.invalid"],
            cwd=repository, check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "DOC04A Test"],
            cwd=repository, check=True,
        )
        subprocess.run(
            ["git", "add", "--", *repair_module._CRITICAL_RUNTIME_PATHS],
            cwd=repository, check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "synthetic identity"],
            cwd=repository, check=True,
            capture_output=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repository,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        script = repository / repair_module._CRITICAL_RUNTIME_PATHS[0]
        return repository, script, head

    def test_g21_dirty_critical_script_rejected(self) -> None:
        _, script, head = self._git_repository()
        script.write_bytes(b"synthetic-dirty-script")
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _verify_runtime_source_identity(head, script_path=script)
        self.assertEqual(
            raised.exception.code,
            REPAIR_RUNTIME_SOURCE_MISMATCH,
        )

    def test_g22_dirty_critical_unicode_module_rejected(self) -> None:
        repository, script, head = self._git_repository()
        unicode_module = repository / repair_module._CRITICAL_RUNTIME_PATHS[1]
        unicode_module.write_bytes(b"synthetic-dirty-unicode")
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _verify_runtime_source_identity(head, script_path=script)
        self.assertEqual(
            raised.exception.code,
            REPAIR_RUNTIME_SOURCE_MISMATCH,
        )

    def test_g23_unrelated_dirty_file_does_not_block(self) -> None:
        repository, script, head = self._git_repository()
        (repository / "unrelated.txt").write_text(
            "synthetic dirty", encoding="utf-8"
        )
        normalized = repository / repair_module._CRITICAL_RUNTIME_PATHS[2]
        normalized.write_bytes(
            normalized.read_bytes().replace(b"\n", b"\r\n")
        )
        _verify_runtime_source_identity(head, script_path=script)

    def test_g24_environment_cannot_override_blob_mismatch(self) -> None:
        _, script, head = self._git_repository()
        script.write_bytes(b"synthetic-environment-bypass")
        with patch.dict(
            os.environ,
            {"NEXT_STABIL_RUNTIME_GIT_SHA": head},
        ):
            with self.assertRaises(DocumentMetadataRepairError) as raised:
                _verify_runtime_source_identity(head, script_path=script)
        self.assertEqual(
            raised.exception.code,
            REPAIR_RUNTIME_SOURCE_MISMATCH,
        )

    def test_g35_all_precommit_guards_are_revalidated(self) -> None:
        initial = self._evidence()
        connection = MagicMock()
        connection.execute.return_value = _ScalarResult(
            UPDATED_AT + timedelta(minutes=5)
        )
        with (
            patch.object(repair_module, "_assert_no_active_operations") as operations,
            patch.object(repair_module, "_reload_target_state", return_value={}) as target_state,
            patch.object(repair_module, "_assert_target_quiescent") as target,
            patch.object(repair_module, "_verify_runtime_source_identity") as identity,
            patch.object(repair_module, "_load_backup_evidence", return_value=initial) as load,
            patch.object(repair_module, "_validate_backup_evidence") as logical,
            patch.object(repair_module, "_verify_backup_physical") as physical,
        ):
            _revalidate_production_guards(
                connection,
                contract=self._contract(initial),
                initial_backup=initial,
            )
        operations.assert_called_once()
        target_state.assert_called_once()
        target.assert_called_once()
        identity.assert_called_once()
        load.assert_called_once()
        logical.assert_called_once()
        physical.assert_called_once()
        self.assertTrue(physical.call_args.kwargs["recheck"])


class DocumentMetadataRepairIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        assert_isolated_database(engine, TEST_DATABASE_NAME)
        with engine.connect() as connection:
            head = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        if head != EXPECTED_HEAD:
            raise AssertionError("isolated database revision mismatch")

    def setUp(self) -> None:
        self.storage = tempfile.TemporaryDirectory()
        self.data_root = Path(self.storage.name)
        self._cleanup_operation_fixtures()
        self._cleanup_documents()
        self._seed_document()

    def tearDown(self) -> None:
        self._cleanup_operation_fixtures()
        self._cleanup_documents()
        self.storage.cleanup()

    def _cleanup_operation_fixtures(self) -> None:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM restore_runs "
                    "WHERE error_code LIKE 'doc04a3-%'"
                )
            )
            connection.execute(
                text(
                    "DELETE FROM backup_runs "
                    "WHERE error_code LIKE 'doc04a3-%'"
                )
            )
            connection.execute(
                text("DELETE FROM users WHERE username=:username"),
                {"username": OPERATION_FIXTURE_USER},
            )
            connection.execute(
                text("DELETE FROM roles WHERE name=:name"),
                {"name": OPERATION_FIXTURE_ROLE},
            )

    @staticmethod
    def _operation_actor(connection) -> int:
        role_id = connection.execute(
            text(
                "INSERT INTO roles (name, description) "
                "VALUES (:name, 'isolated DOC04A3 fixture') RETURNING id"
            ),
            {"name": OPERATION_FIXTURE_ROLE},
        ).scalar_one()
        return int(
            connection.execute(
                text(
                    "INSERT INTO users ("
                    "username, email, password_hash, is_active, "
                    "must_change_password, password_reset_requested, "
                    "auth_version, role_id"
                    ") VALUES ("
                    ":username, 'doc04a3@example.invalid', "
                    "'isolated-not-a-password', true, false, false, 0, "
                    ":role_id) RETURNING id"
                ),
                {
                    "username": OPERATION_FIXTURE_USER,
                    "role_id": role_id,
                },
            ).scalar_one()
        )

    def _cleanup_documents(self) -> None:
        with engine.begin() as connection:
            for table in (
                "document_intelligence_artifacts",
                "document_preparation_jobs",
                "document_chunks",
                "document_assets",
                "document_pages",
            ):
                connection.execute(
                    text(
                        f"DELETE FROM {table} "
                        "WHERE document_id IN (:target, :other)"
                    ),
                    {"target": TARGET_ID, "other": OTHER_ID},
                )
            connection.execute(
                text(
                    "DELETE FROM documents "
                    "WHERE id IN (:target, :other)"
                ),
                {"target": TARGET_ID, "other": OTHER_ID},
            )

    def _seed_document(
        self,
        *,
        document_id: int = TARGET_ID,
        raw_text: str = RAW_FIXTURE,
        normalized_text: str = NORMALIZED_FIXTURE,
        file_content: bytes = FILE_CONTENT,
    ) -> Path:
        relative = Path("documents") / f"synthetic-{document_id}.bin"
        source = self.data_root / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(file_content)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO documents ("
                    "id, filename, original_filename, content_type, "
                    "file_size, storage_path, checksum_sha256, source_type, "
                    "processing_status, metadata_status, metadata_raw, "
                    "metadata_normalized, match_status, created_at, updated_at"
                    ") VALUES ("
                    ":id, :filename, :filename, 'application/octet-stream', "
                    ":file_size, :storage_path, :checksum, 'manual_upload', "
                    "'processed', 'processed', CAST(:raw AS json), "
                    "CAST(:normalized AS json), 'unmatched', :updated_at, "
                    ":updated_at)"
                ),
                {
                    "id": document_id,
                    "filename": f"synthetic-{document_id}.bin",
                    "file_size": len(file_content),
                    "storage_path": relative.as_posix(),
                    "checksum": _sha256(file_content),
                    "raw": raw_text,
                    "normalized": normalized_text,
                    "updated_at": UPDATED_AT,
                },
            )
        return source

    def _row(self) -> dict[str, object]:
        with engine.connect() as connection:
            return dict(
                connection.execute(
                    text(
                        "SELECT xmin::text AS xmin, updated_at, "
                        "metadata_raw::text AS metadata_raw, "
                        "metadata_normalized::text AS metadata_normalized, "
                        "checksum_sha256, file_size "
                        "FROM documents WHERE id=:id"
                    ),
                    {"id": TARGET_ID},
                ).mappings().one()
            )

    def _contract(self, **changes: object) -> RepairContract:
        row = self._row()
        raw = str(row["metadata_raw"])
        normalized = str(row["metadata_normalized"])
        raw_result = repair_json_text_surrogates(raw)
        normalized_result = repair_json_text_surrogates(normalized)
        contract = RepairContract(
            expected_database=TEST_DATABASE_NAME,
            expected_alembic_head=EXPECTED_HEAD,
            expected_xmin=str(row["xmin"]),
            expected_updated_at=row["updated_at"],
            expected_storage_sha256=str(row["checksum_sha256"]),
            expected_raw_before_sha256=raw_result.before_sha256,
            expected_raw_candidate_sha256=raw_result.after_sha256,
            expected_normalized_before_sha256=(
                normalized_result.before_sha256
            ),
            expected_normalized_candidate_sha256=(
                normalized_result.after_sha256
            ),
        )
        return replace(contract, **changes)

    def _execute(
        self,
        *,
        contract: RepairContract | None = None,
        execute: bool,
        production_preflight: bool = False,
    ) -> RepairResult:
        with engine.connect() as connection:
            return execute_repair(
                connection,
                contract=contract or self._contract(),
                data_root=self.data_root,
                execute=execute,
                production_preflight=production_preflight,
            )

    def _state(self) -> tuple[object, ...]:
        row = self._row()
        return (
            row["xmin"],
            row["updated_at"],
            row["metadata_raw"],
            row["metadata_normalized"],
            row["checksum_sha256"],
            row["file_size"],
        )

    def _assert_code(
        self,
        expected: str,
        *,
        contract: RepairContract | None = None,
        execute: bool = True,
    ) -> None:
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            self._execute(contract=contract, execute=execute)
        self.assertEqual(raised.exception.code, expected)

    def _seed_preparation_job(
        self,
        *,
        status: str,
        generation: str,
    ) -> None:
        stage = {
            "queued": "queued",
            "running": "local_analysis",
            "ready": "ready_for_ai",
            "failed": "failed",
        }[status]
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO document_preparation_jobs ("
                    "id, document_id, input_checksum, processor_generation, "
                    "trigger, priority, status, stage, attempt_count, "
                    "max_attempts) VALUES ("
                    ":id, :document_id, :checksum, :generation, "
                    "'operator_retry', 2, :status, :stage, 0, 3)"
                ),
                {
                    "id": f"doc04a1-{generation}",
                    "document_id": TARGET_ID,
                    "checksum": _sha256(FILE_CONTENT),
                    "generation": generation,
                    "status": status,
                    "stage": stage,
                },
            )

    @staticmethod
    def _after_current_database_listener(
        action,
        statements: list[str],
    ):
        fired = [False]

        def listener(
            _connection, _cursor, statement, _parameters, _context,
            _executemany,
        ) -> None:
            normalized = " ".join(statement.split())
            statements.append(normalized)
            if not fired[0] and "SELECT current_database()" in normalized:
                fired[0] = True
                action()

        return listener, fired

    def _commit_running_backup(self, suffix: str) -> None:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                _acquire_backup_restore_operation_lock(connection)
                actor_id = self._operation_actor(connection)
                connection.execute(
                    text(
                        "INSERT INTO backup_runs ("
                        "scope, trigger, destination, status, stage, "
                        "created_by_user_id, error_code"
                        ") VALUES ("
                        "'database', 'manual', 'synthetic-isolated', "
                        "'running', 'database', :actor_id, :error_code)"
                    ),
                    {
                        "actor_id": actor_id,
                        "error_code": f"doc04a3-{suffix}",
                    },
                )
                transaction.commit()
            except Exception:
                transaction.rollback()
                raise

    def _commit_unresolved_restore(self, suffix: str) -> None:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                _acquire_backup_restore_operation_lock(connection)
                actor_id = self._operation_actor(connection)
                connection.execute(
                    text(
                        "INSERT INTO restore_runs ("
                        "checkpoint_path, mode, status, stage, "
                        "manifest_verified, compatibility_verified, "
                        "compatibility_result, created_by_user_id, "
                        "error_code"
                        ") VALUES ("
                        "'synthetic-isolated', 'database', "
                        "'approval_required', 'approval_required', "
                        "false, false, 'invalid', :actor_id, :error_code)"
                    ),
                    {
                        "actor_id": actor_id,
                        "error_code": f"doc04a3-{suffix}",
                    },
                )
                transaction.commit()
            except Exception:
                transaction.rollback()
                raise

    @staticmethod
    def _commit_preparation_insert(suffix: str) -> None:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO document_preparation_jobs ("
                    "id, document_id, input_checksum, processor_generation, "
                    "trigger, priority, status, stage, attempt_count, "
                    "max_attempts) VALUES ("
                    ":id, :document_id, :checksum, :generation, "
                    "'operator_retry', 2, 'queued', 'queued', 0, 3)"
                ),
                {
                    "id": f"doc04a3-{suffix}",
                    "document_id": TARGET_ID,
                    "checksum": _sha256(FILE_CONTENT),
                    "generation": suffix,
                },
            )

    def _store_repository_metadata(
        self,
        payload: dict[str, object],
        *,
        updated_payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        with SessionLocal() as session:
            repository = DocumentRepository(session)
            document = Document(
                id=OTHER_ID,
                filename="synthetic-jsonb.json",
                original_filename="synthetic-jsonb.json",
                content_type="application/json",
                file_size=0,
                source_type="manual_upload",
                processing_status="processed",
                metadata_status="processed",
                metadata_raw=payload,
                metadata_normalized=payload,
                match_status="unmatched",
            )
            repository.create(document)
            session.commit()
            if updated_payload is not None:
                stored = repository.get(OTHER_ID)
                if stored is None:
                    raise AssertionError("synthetic document missing")
                repository.update_metadata(
                    document=stored,
                    status="processed",
                    raw_metadata=updated_payload,
                    normalized_metadata=updated_payload,
                    error=None,
                )
                session.commit()
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT pg_typeof(metadata_raw)::text AS column_type, "
                    "metadata_raw::jsonb AS as_jsonb, "
                    "jsonb_typeof(metadata_raw::jsonb) AS jsonb_type "
                    "FROM documents WHERE id=:id"
                ),
                {"id": OTHER_ID},
            ).mappings().one()
        return dict(row)

    def test_r13_default_cli_mode_rolls_back(self) -> None:
        required = [
            "--expected-database", TEST_DATABASE_NAME,
            "--expected-alembic-head", EXPECTED_HEAD,
            "--expected-xmin", "1",
            "--expected-updated-at", UPDATED_AT.isoformat(),
            "--expected-storage-sha256", "0" * 64,
            "--expected-raw-before-sha256", "0" * 64,
            "--expected-raw-candidate-sha256", "0" * 64,
            "--expected-normalized-before-sha256", "0" * 64,
            "--expected-normalized-candidate-sha256", "0" * 64,
        ]
        self.assertFalse(_parser().parse_args(required).execute)
        before = self._state()
        result = self._execute(execute=False)
        self.assertFalse(result.executed)
        self.assertEqual(self._state(), before)

    def test_r14_execute_updates_one_row_and_two_columns(self) -> None:
        before = self._state()
        result = self._execute(execute=True)
        after = self._state()
        self.assertTrue(result.executed)
        self.assertEqual(result.affected_documents, 1)
        self.assertEqual(
            result.affected_columns,
            ("metadata_normalized", "metadata_raw"),
        )
        self.assertNotEqual(after[2:4], before[2:4])
        self.assertEqual(after[1], before[1])
        self.assertEqual(after[4:], before[4:])

    def test_r15_wrong_raw_before_hash_refuses(self) -> None:
        self._assert_code(
            REPAIR_BEFORE_HASH,
            contract=self._contract(
                expected_raw_before_sha256="0" * 64
            ),
        )

    def test_r16_wrong_normalized_before_hash_refuses(self) -> None:
        self._assert_code(
            REPAIR_BEFORE_HASH,
            contract=self._contract(
                expected_normalized_before_sha256="0" * 64
            ),
        )

    def test_r17_wrong_candidate_hash_refuses(self) -> None:
        self._assert_code(
            REPAIR_CANDIDATE_HASH,
            contract=self._contract(
                expected_raw_candidate_sha256="0" * 64
            ),
        )

    def test_r18_wrong_xmin_refuses(self) -> None:
        self._assert_code(
            REPAIR_CONCURRENCY,
            contract=self._contract(expected_xmin="0"),
        )

    def test_r19_wrong_updated_at_refuses(self) -> None:
        self._assert_code(
            REPAIR_CONCURRENCY,
            contract=self._contract(
                expected_updated_at=UPDATED_AT - timedelta(seconds=1)
            ),
        )

    def test_r20_storage_checksum_mismatch_refuses(self) -> None:
        self._assert_code(
            REPAIR_STORAGE,
            contract=self._contract(
                expected_storage_sha256="0" * 64
            ),
        )

    def test_r21_missing_storage_file_refuses(self) -> None:
        contract = self._contract()
        source = self.data_root / "documents" / f"synthetic-{TARGET_ID}.bin"
        source.unlink()
        self._assert_code(REPAIR_STORAGE, contract=contract)

    def test_r22_zero_affected_row_refuses(self) -> None:
        contract = self._contract()
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM documents WHERE id=:id"),
                {"id": TARGET_ID},
            )
        self._assert_code(REPAIR_TARGET_MISSING, contract=contract)

    def test_r23_second_affected_document_refuses(self) -> None:
        self._seed_document(document_id=OTHER_ID)
        self._assert_code(REPAIR_SCOPE, contract=self._contract())

    def test_r24_post_json_validation_failure_rolls_back(self) -> None:
        before = self._state()
        contract = self._contract()
        original = repair_module.repair_json_text_surrogates

        def fail_post(value: str):
            result = original(value)
            if (
                result.before_sha256
                == contract.expected_raw_candidate_sha256
                and result.replacement_count == 0
            ):
                return replace(result, before_sha256="0" * 64)
            return result

        with patch.object(
            repair_module,
            "repair_json_text_surrogates",
            side_effect=fail_post,
        ):
            self._assert_code(REPAIR_POSTCONDITION, contract=contract)
        self.assertEqual(self._state(), before)

    def test_r25_two_row_update_is_impossible(self) -> None:
        self._seed_document(
            document_id=OTHER_ID,
            raw_text=SAFE_FIXTURE,
            normalized_text=SAFE_FIXTURE,
        )
        with engine.connect() as connection:
            other_before = tuple(
                connection.execute(
                    text(
                        "SELECT xmin::text, metadata_raw::text, "
                        "metadata_normalized::text, updated_at "
                        "FROM documents WHERE id=:id"
                    ),
                    {"id": OTHER_ID},
                ).one()
            )
        self._execute(execute=True)
        with engine.connect() as connection:
            other_after = tuple(
                connection.execute(
                    text(
                        "SELECT xmin::text, metadata_raw::text, "
                        "metadata_normalized::text, updated_at "
                        "FROM documents WHERE id=:id"
                    ),
                    {"id": OTHER_ID},
                ).one()
            )
        self.assertEqual(other_after, other_before)

    def test_r26_second_execute_refuses_old_before_hash(self) -> None:
        original_contract = self._contract()
        self._execute(contract=original_contract, execute=True)
        refreshed = self._contract(
            expected_raw_before_sha256=(
                original_contract.expected_raw_before_sha256
            ),
            expected_normalized_before_sha256=(
                original_contract.expected_normalized_before_sha256
            ),
            expected_raw_candidate_sha256=(
                original_contract.expected_raw_candidate_sha256
            ),
            expected_normalized_candidate_sha256=(
                original_contract.expected_normalized_candidate_sha256
            ),
        )
        self._assert_code(REPAIR_BEFORE_HASH, contract=refreshed)

    def test_r27_relations_and_file_checksum_unchanged(self) -> None:
        source = self.data_root / "documents" / f"synthetic-{TARGET_ID}.bin"
        before_hash = _sha256(source.read_bytes())
        with engine.connect() as connection:
            relations_before = repair_module._relation_counts(connection)
        self._execute(execute=True)
        with engine.connect() as connection:
            relations_after = repair_module._relation_counts(connection)
        self.assertEqual(relations_after, relations_before)
        self.assertEqual(_sha256(source.read_bytes()), before_hash)

    def test_r28_production_name_guard_requires_allow(self) -> None:
        connection = MagicMock()
        contract = self._production_contract(
            allow_production_ai_lab=False,
            owner_approval_id="synthetic-approval",
            verified_backup_run_id=1,
            verified_backup_manifest_sha256="a" * 64,
        )
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _validate_production_gate(
                connection,
                database="ai_lab",
                production_mode=True,
                contract=contract,
            )
        self.assertEqual(raised.exception.code, REPAIR_PRODUCTION_GUARD)
        connection.execute.assert_not_called()

    def test_r29_production_guard_requires_owner(self) -> None:
        connection = MagicMock()
        contract = self._production_contract(
            allow_production_ai_lab=True,
            owner_approval_id=None,
            verified_backup_run_id=1,
            verified_backup_manifest_sha256="a" * 64,
        )
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _validate_production_gate(
                connection,
                database="ai_lab",
                production_mode=True,
                contract=contract,
            )
        self.assertEqual(raised.exception.code, REPAIR_PRODUCTION_GUARD)
        connection.execute.assert_not_called()

    def test_r30_production_guard_requires_backup(self) -> None:
        connection = MagicMock()
        contract = self._production_contract(
            allow_production_ai_lab=True,
            owner_approval_id="synthetic-approval",
            verified_backup_run_id=None,
            verified_backup_manifest_sha256=None,
        )
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _validate_production_gate(
                connection,
                database="ai_lab",
                production_mode=True,
                contract=contract,
            )
        self.assertEqual(raised.exception.code, REPAIR_PRODUCTION_GUARD)
        connection.execute.assert_not_called()

    def test_r31_wrong_alembic_head_refuses(self) -> None:
        self._assert_code(
            REPAIR_ALEMBIC_MISMATCH,
            contract=self._contract(
                expected_alembic_head="synthetic_wrong_head"
            ),
        )

    def test_r32_active_backup_or_restore_refuses(self) -> None:
        connection = MagicMock()
        connection.execute.side_effect = [
            _ScalarResult(1),
            _ScalarResult(0),
        ]
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _assert_no_active_operations(connection)
        self.assertEqual(raised.exception.code, REPAIR_ACTIVE_OPERATION)

    def test_r33_output_contains_no_metadata_value(self) -> None:
        marker = "synthetic-private-marker"
        lexical = repair_json_text_surrogates(
            '{"x":"' + marker + r'-\uDC00"}'
        )
        result = RepairResult(
            code="DOCUMENT_METADATA_REPAIR_DRY_RUN",
            database=TEST_DATABASE_NAME,
            executed=False,
            raw=lexical.safe_evidence(),
            normalized=lexical.safe_evidence(),
            affected_documents=1,
            affected_columns=("metadata_raw", "metadata_normalized"),
        )
        output = json.dumps(result.safe_payload(), sort_keys=True)
        self.assertNotIn(marker, output)
        self.assertNotIn("candidate_text", output)

    def test_r34_transaction_failure_restores_exact_state(self) -> None:
        before = self._state()
        with patch.object(
            repair_module.Session,
            "get",
            side_effect=RuntimeError("synthetic postcondition failure"),
        ):
            with self.assertRaises(RuntimeError):
                self._execute(execute=True)
        self.assertEqual(self._state(), before)

    def test_r35_database_is_disposable_and_isolated(self) -> None:
        self.assertEqual(
            assert_isolated_database(engine, TEST_DATABASE_NAME),
            TEST_DATABASE_NAME,
        )
        self.assertNotEqual(TEST_DATABASE_NAME, "ai_lab")

    def test_g25_active_target_preparation_queued_rejected(self) -> None:
        self._seed_preparation_job(status="queued", generation="g25")
        self._assert_code(REPAIR_TARGET_ACTIVE)

    def test_g26_active_target_preparation_running_rejected(self) -> None:
        self._seed_preparation_job(status="running", generation="g26")
        self._assert_code(REPAIR_TARGET_ACTIVE)

    def test_g27_historical_preparation_does_not_block(self) -> None:
        self._seed_preparation_job(status="ready", generation="g27-ready")
        self._seed_preparation_job(status="failed", generation="g27-failed")
        result = self._execute(execute=False)
        self.assertFalse(result.executed)

    def test_g28_target_processing_or_metadata_mismatch_rejected(self) -> None:
        for column, value in (
            ("processing_status", "pending"),
            ("metadata_status", "failed"),
        ):
            with self.subTest(column=column):
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            f"UPDATE documents SET {column}=:value "
                            "WHERE id=:id"
                        ),
                        {"value": value, "id": TARGET_ID},
                    )
                self._assert_code(REPAIR_TARGET_ACTIVE)
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            f"UPDATE documents SET {column}='processed' "
                            "WHERE id=:id"
                        ),
                        {"id": TARGET_ID},
                    )

    def test_g29_target_trashed_or_purged_rejected(self) -> None:
        for column in ("trashed_at", "purged_at"):
            with self.subTest(column=column):
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            f"UPDATE documents SET {column}=:value "
                            "WHERE id=:id"
                        ),
                        {"value": UPDATED_AT, "id": TARGET_ID},
                    )
                self._assert_code(REPAIR_TARGET_ACTIVE)
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            f"UPDATE documents SET {column}=NULL "
                            "WHERE id=:id"
                        ),
                        {"id": TARGET_ID},
                    )

    def test_g30_sanitized_isolated_surrogates_jsonb_roundtrip(self) -> None:
        created = sanitize_json_compatible(
            {"low": "left\udc00right", "existing": "\ufffd"}
        )
        updated = sanitize_json_compatible(
            {"high": "left\ud800right", "existing": "\ufffd"}
        )
        row = self._store_repository_metadata(
            created,
            updated_payload=updated,
        )
        self.assertEqual(row["column_type"], "json")
        self.assertEqual(row["jsonb_type"], "object")
        self.assertEqual(
            row["as_jsonb"],
            {"high": "left\ufffdright", "existing": "\ufffd"},
        )

    def test_g31_valid_surrogate_pair_jsonb_roundtrip(self) -> None:
        pair = "\ud83d\ude00"
        payload = sanitize_json_compatible({"pair": pair})
        self.assertEqual(payload["pair"], pair)
        row = self._store_repository_metadata(payload)
        self.assertEqual(row["as_jsonb"], {"pair": "\U0001f600"})

    def test_g32_polish_and_supplementary_jsonb_roundtrip(self) -> None:
        payload = sanitize_json_compatible(
            {"polish": "Za\u017c\u00f3\u0142\u0107 g\u0119\u015bl\u0105 ja\u017a\u0144", "scalar": "\U0001f9ea"}
        )
        row = self._store_repository_metadata(payload)
        self.assertEqual(row["as_jsonb"], payload)

    def test_g33_dynamic_sanitized_key_jsonb_roundtrip(self) -> None:
        payload = sanitize_json_compatible({"dynamic\udc00key": "safe"})
        row = self._store_repository_metadata(payload)
        self.assertEqual(row["as_jsonb"], {"dynamic\ufffdkey": "safe"})
        with engine.connect() as connection:
            present = connection.execute(
                text(
                    "SELECT metadata_raw::jsonb ? :key "
                    "FROM documents WHERE id=:id"
                ),
                {"key": "dynamic\ufffdkey", "id": OTHER_ID},
            ).scalar_one()
        self.assertTrue(present)

    def test_g34_nul_is_replaced_and_jsonb_operator_safe(self) -> None:
        sanitized_text = sanitize_metadata_text("before\x00after")
        self.assertEqual(sanitized_text.value, "before\ufffdafter")
        self.assertEqual(sanitized_text.stats.replaced_nul, 1)
        self.assertEqual(sanitized_text.stats.replacement_count, 1)
        with self.assertRaises(DocumentMetadataSafetyError):
            assert_json_compatible_safe({"nul": "before\x00after"})
        payload = sanitize_json_compatible(
            {"nul": "before\x00after", "key\x00": "value"}
        )
        row = self._store_repository_metadata(payload)
        self.assertEqual(
            row["as_jsonb"],
            {"nul": "before\ufffdafter", "key\ufffd": "value"},
        )
        with engine.connect() as connection:
            value = connection.execute(
                text(
                    "SELECT metadata_raw::jsonb ->> :key "
                    "FROM documents WHERE id=:id"
                ),
                {"key": "nul", "id": OTHER_ID},
            ).scalar_one()
        self.assertEqual(value, "before\ufffdafter")

    def _identity_fixture(
        self,
    ) -> tuple[Path, Path, str, dict[str, str]]:
        repository = self.data_root / "identity-repository"
        committed: dict[str, str] = {}
        for relative in repair_module._CRITICAL_RUNTIME_PATHS:
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            content = ("synthetic:" + relative + "\n").encode()
            path.write_bytes(content)
            blob = b"blob " + str(len(content)).encode() + b"\0" + content
            committed[relative] = hashlib.sha1(blob).hexdigest()
        head = "e" * 40
        script = repository / repair_module._CRITICAL_RUNTIME_PATHS[0]
        return repository, script, head, committed

    @staticmethod
    def _identity_git_output(
        repository: Path,
        head: str,
        committed: dict[str, str],
    ):
        def output(arguments, *, cwd, text_output):
            del cwd, text_output
            if arguments == ["rev-parse", "--show-toplevel"]:
                return str(repository)
            if arguments == ["rev-parse", "HEAD"]:
                return head
            if arguments[:1] == ["rev-parse"]:
                relative = arguments[1].split(":", 1)[1]
                return committed[relative]
            if arguments[:1] == ["hash-object"]:
                relative = arguments[1].split("=", 1)[1]
                content = (repository / relative).read_bytes()
                blob = (
                    b"blob " + str(len(content)).encode() + b"\0" + content
                )
                return hashlib.sha1(blob).hexdigest()
            raise AssertionError(f"unexpected Git command: {arguments!r}")

        return output

    @staticmethod
    def _required_cli_arguments() -> list[str]:
        return [
            "--expected-database", TEST_DATABASE_NAME,
            "--expected-alembic-head", EXPECTED_HEAD,
            "--expected-xmin", "1",
            "--expected-updated-at", UPDATED_AT.isoformat(),
            "--expected-storage-sha256", "0" * 64,
            "--expected-raw-before-sha256", "0" * 64,
            "--expected-raw-candidate-sha256", "0" * 64,
            "--expected-normalized-before-sha256", "0" * 64,
            "--expected-normalized-candidate-sha256", "0" * 64,
        ]

    def test_h01_canonical_operation_lock_identity(self) -> None:
        self.assertEqual(repair_module.OPERATION_LOCK_KEY, OPERATION_LOCK_KEY)
        source = Path(repair_module.__file__).read_text(encoding="utf-8")
        self.assertIn(
            "from app.services.backup_restore_service import OPERATION_LOCK_KEY",
            source,
        )
        self.assertIn(
            "backend/app/services/backup_restore_service.py",
            repair_module._CRITICAL_RUNTIME_PATHS,
        )

    def test_h02_repair_acquires_operation_lock(self) -> None:
        with engine.connect() as first, engine.connect() as second:
            first_transaction = first.begin()
            second_transaction = second.begin()
            try:
                _acquire_backup_restore_operation_lock(first)
                acquired = second.execute(
                    text("SELECT pg_try_advisory_xact_lock(:key)"),
                    {"key": OPERATION_LOCK_KEY},
                ).scalar_one()
                self.assertFalse(acquired)
            finally:
                second_transaction.rollback()
                first_transaction.rollback()

    def test_h03_busy_lock_refuses_before_target_work(self) -> None:
        statements: list[str] = []
        contract = self._contract()

        def record_statement(
            _connection, _cursor, statement, _parameters, _context,
            _executemany,
        ) -> None:
            statements.append(statement)

        with engine.connect() as holder:
            holder_transaction = holder.begin()
            try:
                _acquire_backup_restore_operation_lock(holder)
                event.listen(engine, "before_cursor_execute", record_statement)
                try:
                    with self.assertRaises(
                        DocumentMetadataRepairError
                    ) as raised:
                        self._execute(contract=contract, execute=True)
                finally:
                    event.remove(
                        engine, "before_cursor_execute", record_statement
                    )
                self.assertEqual(
                    raised.exception.code,
                    REPAIR_OPERATION_LOCK_BUSY,
                )
            finally:
                holder_transaction.rollback()
        self.assertFalse(
            any("FROM documents" in statement for statement in statements)
        )

    def test_h04_operation_lock_released_on_preflight_rollback(self) -> None:
        result = self._execute(
            execute=False,
            production_preflight=True,
        )
        self.assertFalse(result.executed)
        with engine.begin() as connection:
            acquired = connection.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": OPERATION_LOCK_KEY},
            ).scalar_one()
            self.assertTrue(acquired)

    def test_h05_operation_lock_released_on_execute_commit(self) -> None:
        self._execute(execute=True)
        with engine.begin() as connection:
            acquired = connection.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": OPERATION_LOCK_KEY},
            ).scalar_one()
            self.assertTrue(acquired)

    def test_h06_backup_start_race_is_closed(self) -> None:
        with engine.connect() as repair, engine.connect() as backup:
            repair_transaction = repair.begin()
            backup_transaction = backup.begin()
            try:
                _acquire_backup_restore_operation_lock(repair)
                backup_can_start = backup.execute(
                    text("SELECT pg_try_advisory_xact_lock(:key)"),
                    {"key": OPERATION_LOCK_KEY},
                ).scalar_one()
                self.assertFalse(backup_can_start)
            finally:
                backup_transaction.rollback()
                repair_transaction.rollback()
        with engine.begin() as backup:
            backup_can_start = backup.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": OPERATION_LOCK_KEY},
            ).scalar_one()
            self.assertTrue(backup_can_start)

    def test_h07_operation_wins_first_and_repair_reads_no_target(self) -> None:
        statements: list[str] = []
        contract = self._contract()

        def record_statement(
            _connection, _cursor, statement, _parameters, _context,
            _executemany,
        ) -> None:
            statements.append(statement)

        with engine.connect() as operation:
            operation_transaction = operation.begin()
            try:
                _acquire_backup_restore_operation_lock(operation)
                event.listen(engine, "before_cursor_execute", record_statement)
                try:
                    with self.assertRaises(
                        DocumentMetadataRepairError
                    ) as raised:
                        self._execute(
                            contract=contract,
                            execute=False,
                            production_preflight=True,
                        )
                finally:
                    event.remove(
                        engine, "before_cursor_execute", record_statement
                    )
                self.assertEqual(
                    raised.exception.code,
                    REPAIR_OPERATION_LOCK_BUSY,
                )
            finally:
                operation_transaction.rollback()
        self.assertFalse(
            any("FROM documents" in statement for statement in statements)
        )

    def test_h08_repair_lock_order_is_canonical(self) -> None:
        statements: list[str] = []

        def record_statement(
            _connection, _cursor, statement, _parameters, _context,
            _executemany,
        ) -> None:
            statements.append(" ".join(statement.split()))

        def synthetic_backup(connection, **_kwargs):
            connection.execute(
                text("SELECT 1 /* selected_backup_evidence */")
            )
            return None

        event.listen(engine, "before_cursor_execute", record_statement)
        try:
            with patch.object(
                repair_module,
                "_validate_production_gate",
                side_effect=synthetic_backup,
            ):
                self._execute(
                    execute=False,
                    production_preflight=True,
                )
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)
        lock_index = next(
            index for index, value in enumerate(statements)
            if "pg_try_advisory_xact_lock" in value
        )
        backup_index = next(
            index for index, value in enumerate(statements)
            if "selected_backup_evidence" in value
        )
        document_index = next(
            index for index, value in enumerate(statements)
            if "FROM documents WHERE id=" in value and "FOR UPDATE" in value
        )
        preparation_index = next(
            index for index, value in enumerate(statements)
            if "FROM document_preparation_jobs" in value
            and "FOR SHARE" in value
        )
        self.assertLess(lock_index, backup_index)
        self.assertLess(backup_index, document_index)
        self.assertLess(document_index, preparation_index)

    def test_h09_all_terminal_preparation_rows_are_locked(self) -> None:
        self._seed_preparation_job(status="ready", generation="h09-ready")
        self._seed_preparation_job(status="failed", generation="h09-failed")
        with engine.connect() as repair, engine.connect() as contender:
            repair_transaction = repair.begin()
            contender_transaction = contender.begin()
            try:
                _acquire_backup_restore_operation_lock(repair)
                row = repair.execute(
                    text(
                        "SELECT processing_status, metadata_status, "
                        "trashed_at, purged_at FROM documents "
                        "WHERE id=:id FOR UPDATE"
                    ),
                    {"id": TARGET_ID},
                ).mappings().one()
                _assert_target_quiescent(repair, dict(row))
                contender.execute(text("SET LOCAL lock_timeout='200ms'"))
                with self.assertRaises(OperationalError):
                    contender.execute(
                        text(
                            "UPDATE document_preparation_jobs "
                            "SET status='queued' "
                            "WHERE id=:id"
                        ),
                        {"id": "doc04a1-h09-ready"},
                    )
            finally:
                contender_transaction.rollback()
                repair_transaction.rollback()

    def test_h10_queued_and_running_preparation_are_rejected(self) -> None:
        self._seed_preparation_job(status="queued", generation="h10-queued")
        self._seed_preparation_job(status="running", generation="h10-running")
        self._assert_code(
            REPAIR_TARGET_ACTIVE,
            execute=False,
        )

    def test_h11_terminal_preparation_rows_are_allowed(self) -> None:
        self._seed_preparation_job(status="ready", generation="h11-ready")
        self._seed_preparation_job(status="failed", generation="h11-failed")
        result = self._execute(
            execute=False,
            production_preflight=True,
        )
        self.assertEqual(
            result.code,
            "DOCUMENT_METADATA_REPAIR_PRODUCTION_PREFLIGHT_OK",
        )

    def test_h12_new_preparation_insert_is_fenced(self) -> None:
        with engine.connect() as repair, engine.connect() as contender:
            repair_transaction = repair.begin()
            contender_transaction = contender.begin()
            try:
                repair.execute(
                    text("SELECT id FROM documents WHERE id=:id FOR UPDATE"),
                    {"id": TARGET_ID},
                ).one()
                contender.execute(text("SET LOCAL lock_timeout='200ms'"))
                with self.assertRaises(OperationalError):
                    contender.execute(
                        text(
                            "INSERT INTO document_preparation_jobs ("
                            "id, document_id, input_checksum, "
                            "processor_generation, trigger, priority, "
                            "status, stage, attempt_count, max_attempts"
                            ") VALUES ("
                            ":id, :document_id, :checksum, :generation, "
                            "'operator_retry', 2, 'ready', "
                            "'ready_for_ai', 0, 3)"
                        ),
                        {
                            "id": "doc04a1-h12-insert",
                            "document_id": TARGET_ID,
                            "checksum": _sha256(FILE_CONTENT),
                            "generation": "h12-insert",
                        },
                    )
            finally:
                contender_transaction.rollback()
                repair_transaction.rollback()

    def test_h13_preparation_locks_release_after_rollback(self) -> None:
        self._seed_preparation_job(status="ready", generation="h13-ready")
        with engine.connect() as repair:
            repair_transaction = repair.begin()
            row = repair.execute(
                text(
                    "SELECT processing_status, metadata_status, "
                    "trashed_at, purged_at FROM documents "
                    "WHERE id=:id FOR UPDATE"
                ),
                {"id": TARGET_ID},
            ).mappings().one()
            _assert_target_quiescent(repair, dict(row))
            repair_transaction.rollback()
        with engine.begin() as connection:
            changed = connection.execute(
                text(
                    "UPDATE document_preparation_jobs SET status='failed' "
                    "WHERE id=:id"
                ),
                {"id": "doc04a1-h13-ready"},
            )
            self.assertEqual(changed.rowcount, 1)
            connection.execute(
                text(
                    "INSERT INTO document_preparation_jobs ("
                    "id, document_id, input_checksum, processor_generation, "
                    "trigger, priority, status, stage, attempt_count, "
                    "max_attempts) VALUES ("
                    ":id, :document_id, :checksum, :generation, "
                    "'operator_retry', 2, 'ready', 'ready_for_ai', 0, 3)"
                ),
                {
                    "id": "doc04a1-h13-insert",
                    "document_id": TARGET_ID,
                    "checksum": _sha256(FILE_CONTENT),
                    "generation": "h13-insert",
                },
            )

    def test_h14_execute_and_preflight_flags_are_exclusive(self) -> None:
        with self.assertRaises(SystemExit):
            _parser().parse_args(
                ["--execute", "--preflight-production"]
                + self._required_cli_arguments()
            )

    def test_h15_production_default_refuses_before_target_read(self) -> None:
        connection = MagicMock()
        connection.in_transaction.return_value = False
        connection.execution_options.return_value = connection
        transaction = connection.begin.return_value
        transaction.is_active = True
        connection.execute.side_effect = [
            _ScalarResult("ai_lab"),
            _ScalarResult(UPDATED_AT),
        ]
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            execute_repair(
                connection,
                contract=_guard_contract(),
                data_root=self.data_root,
            )
        self.assertEqual(raised.exception.code, REPAIR_PRODUCTION_GUARD)
        sql = " ".join(
            str(call.args[0]) for call in connection.execute.call_args_list
        )
        self.assertNotIn("FROM documents", sql)

    def test_h16_preflight_requires_production_allow_flag(self) -> None:
        connection = MagicMock()
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _validate_production_gate(
                connection,
                database="ai_lab",
                production_mode=True,
                contract=_guard_contract(allow_production_ai_lab=False),
            )
        self.assertEqual(raised.exception.code, REPAIR_PRODUCTION_GUARD)
        connection.execute.assert_not_called()

    def test_h17_preflight_requires_owner_approval(self) -> None:
        connection = MagicMock()
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _validate_production_gate(
                connection,
                database="ai_lab",
                production_mode=True,
                contract=_guard_contract(owner_approval_id=None),
            )
        self.assertEqual(raised.exception.code, REPAIR_PRODUCTION_GUARD)
        connection.execute.assert_not_called()

    def test_h18_preflight_requires_complete_backup_contract(self) -> None:
        missing_values = (
            {"verified_backup_run_id": None},
            {"verified_backup_manifest_sha256": None},
            {"expected_backup_finished_at": None},
            {"maximum_backup_age_seconds": None},
            {"expected_backup_destination_root_sha256": None},
        )
        for changes in missing_values:
            with self.subTest(changes=changes):
                connection = MagicMock()
                with self.assertRaises(
                    DocumentMetadataRepairError
                ) as raised:
                    _validate_production_gate(
                        connection,
                        database="ai_lab",
                        production_mode=True,
                        contract=_guard_contract(**changes),
                    )
                self.assertEqual(
                    raised.exception.code,
                    REPAIR_PRODUCTION_GUARD,
                )
                connection.execute.assert_not_called()

    def test_h19_preflight_full_contract_is_nonwriting(self) -> None:
        evidence = _backup_evidence(self.data_root)
        contract = _guard_contract(evidence)
        connection = MagicMock()
        with (
            patch.object(repair_module, "_verify_runtime_source_identity") as identity,
            patch.object(
                repair_module,
                "_load_backup_evidence",
                return_value=evidence,
            ) as load,
            patch.object(repair_module, "_validate_backup_evidence") as logical,
            patch.object(repair_module, "_verify_backup_physical") as physical,
        ):
            selected = _validate_production_gate(
                connection,
                database="ai_lab",
                production_mode=True,
                contract=contract,
                transaction_time=UPDATED_AT + timedelta(minutes=5),
            )
        self.assertEqual(selected, evidence)
        identity.assert_called_once()
        load.assert_called_once()
        logical.assert_called_once()
        physical.assert_called_once()

        statements: list[str] = []

        def record_statement(
            _connection, _cursor, statement, _parameters, _context,
            _executemany,
        ) -> None:
            statements.append(" ".join(statement.split()))

        original_assert_candidate = repair_module._assert_candidate
        event.listen(engine, "before_cursor_execute", record_statement)
        try:
            with patch.object(
                repair_module,
                "_assert_candidate",
                wraps=original_assert_candidate,
            ) as candidate:
                result = self._execute(
                    execute=False,
                    production_preflight=True,
                )
        finally:
            event.remove(engine, "before_cursor_execute", record_statement)
        self.assertEqual(candidate.call_count, 2)
        self.assertEqual(
            result.code,
            "DOCUMENT_METADATA_REPAIR_PRODUCTION_PREFLIGHT_OK",
        )
        self.assertFalse(result.executed)
        self.assertTrue(result.production_preflight)
        self.assertFalse(
            any(
                statement.startswith("UPDATE documents")
                for statement in statements
            )
        )

    def test_h20_preflight_holds_lock_until_rollback(self) -> None:
        observed: list[bool] = []
        original_scope_scan = repair_module._scope_scan

        def observe_lock(connection):
            with engine.begin() as observer:
                observed.append(
                    bool(
                        observer.execute(
                            text("SELECT pg_try_advisory_xact_lock(:key)"),
                            {"key": OPERATION_LOCK_KEY},
                        ).scalar_one()
                    )
                )
            return original_scope_scan(connection)

        with patch.object(
            repair_module,
            "_scope_scan",
            side_effect=observe_lock,
        ):
            self._execute(execute=False, production_preflight=True)
        self.assertEqual(observed, [False, False])
        with engine.begin() as observer:
            self.assertTrue(
                observer.execute(
                    text("SELECT pg_try_advisory_xact_lock(:key)"),
                    {"key": OPERATION_LOCK_KEY},
                ).scalar_one()
            )

    def test_h21_preflight_failure_rolls_back_and_releases_lock(self) -> None:
        before = self._state()
        original = repair_module._assert_candidate
        calls = 0

        def fail_after_candidates(*args, **kwargs):
            nonlocal calls
            original(*args, **kwargs)
            calls += 1
            if calls == 2:
                raise DocumentMetadataRepairError(REPAIR_POSTCONDITION)

        with patch.object(
            repair_module,
            "_assert_candidate",
            side_effect=fail_after_candidates,
        ):
            with self.assertRaises(DocumentMetadataRepairError) as raised:
                self._execute(
                    execute=False,
                    production_preflight=True,
                )
        self.assertEqual(raised.exception.code, REPAIR_POSTCONDITION)
        self.assertEqual(self._state(), before)
        with engine.begin() as observer:
            self.assertTrue(
                observer.execute(
                    text("SELECT pg_try_advisory_xact_lock(:key)"),
                    {"key": OPERATION_LOCK_KEY},
                ).scalar_one()
            )

    def test_h22_execute_remains_one_row_two_columns(self) -> None:
        before = self._state()
        result = self._execute(execute=True)
        after = self._state()
        self.assertTrue(result.executed)
        self.assertEqual(result.affected_documents, 1)
        self.assertEqual(
            result.affected_columns,
            ("metadata_normalized", "metadata_raw"),
        )
        self.assertEqual(after[1], before[1])
        self.assertEqual(after[4:], before[4:])

    def test_h23_restore_rollback_required_blocks(self) -> None:
        connection = MagicMock()
        connection.execute.side_effect = [_ScalarResult(0), _ScalarResult(1)]
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _assert_no_active_operations(connection)
        self.assertEqual(raised.exception.code, REPAIR_ACTIVE_OPERATION)
        restore_sql = str(connection.execute.call_args_list[1].args[0])
        self.assertIn("rollback_required", restore_sql)

    def test_h24_restore_approval_required_blocks(self) -> None:
        connection = MagicMock()
        connection.execute.side_effect = [_ScalarResult(0), _ScalarResult(1)]
        with self.assertRaises(DocumentMetadataRepairError) as raised:
            _assert_no_active_operations(connection)
        self.assertEqual(raised.exception.code, REPAIR_ACTIVE_OPERATION)
        restore_sql = str(connection.execute.call_args_list[1].args[0])
        self.assertIn("approval_required", restore_sql)

    def test_h25_terminal_restore_states_do_not_block(self) -> None:
        connection = MagicMock()
        connection.execute.side_effect = [_ScalarResult(0), _ScalarResult(0)]
        _assert_no_active_operations(connection)
        restore_sql = str(connection.execute.call_args_list[1].args[0])
        self.assertNotIn("completed", restore_sql)
        self.assertNotIn("failed", restore_sql)

    def test_h26_dirty_backup_service_rejects_runtime_identity(self) -> None:
        repository, script, head, committed = self._identity_fixture()
        backup_service = (
            repository
            / "backend/app/services/backup_restore_service.py"
        )
        backup_service.write_bytes(b"synthetic-dirty-backup-service")
        with patch.object(
            repair_module,
            "_git_output",
            side_effect=self._identity_git_output(
                repository, head, committed
            ),
        ):
            with self.assertRaises(DocumentMetadataRepairError) as raised:
                _verify_runtime_source_identity(head, script_path=script)
        self.assertEqual(
            raised.exception.code,
            REPAIR_RUNTIME_SOURCE_MISMATCH,
        )

    def test_h27_unrelated_dirty_paths_do_not_block_identity(self) -> None:
        repository, script, head, committed = self._identity_fixture()
        for relative in (
            "backend/test/synthetic_unrelated.py",
            "reports/synthetic-unrelated.md",
            "operations/backup/synthetic-unrelated.txt",
        ):
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic dirty", encoding="utf-8")
        with patch.object(
            repair_module,
            "_git_output",
            side_effect=self._identity_git_output(
                repository, head, committed
            ),
        ):
            _verify_runtime_source_identity(head, script_path=script)

    def test_i01_transaction_is_read_committed(self) -> None:
        observed: list[str] = []
        original = repair_module._assert_no_active_operations

        def observe(connection):
            observed.append(
                str(
                    connection.execute(
                        text("SHOW transaction_isolation")
                    ).scalar_one()
                )
            )
            return original(connection)

        with patch.object(
            repair_module,
            "_assert_no_active_operations",
            side_effect=observe,
        ):
            self._execute(execute=False, production_preflight=True)
        self.assertEqual(REPAIR_TRANSACTION_ISOLATION, "READ COMMITTED")
        self.assertTrue(observed)
        self.assertEqual(set(observed), {"read committed"})
        source = Path(repair_module.__file__).read_text(encoding="utf-8")
        self.assertNotIn('isolation_level="SERIALIZABLE"', source)

    def test_i02_backup_commit_after_first_statement_is_visible(self) -> None:
        contract = self._contract()
        statements: list[str] = []
        listener, fired = self._after_current_database_listener(
            lambda: self._commit_running_backup("i02"),
            statements,
        )
        event.listen(engine, "after_cursor_execute", listener)
        try:
            with self.assertRaises(DocumentMetadataRepairError) as raised:
                self._execute(contract=contract, execute=True)
        finally:
            event.remove(engine, "after_cursor_execute", listener)
        self.assertTrue(fired[0])
        self.assertEqual(raised.exception.code, REPAIR_ACTIVE_OPERATION)
        self.assertFalse(
            any("FROM documents" in statement for statement in statements)
        )

    def test_i03_restore_commit_after_first_statement_is_visible(self) -> None:
        contract = self._contract()
        statements: list[str] = []
        listener, fired = self._after_current_database_listener(
            lambda: self._commit_unresolved_restore("i03"),
            statements,
        )
        event.listen(engine, "after_cursor_execute", listener)
        try:
            with self.assertRaises(DocumentMetadataRepairError) as raised:
                self._execute(contract=contract, execute=True)
        finally:
            event.remove(engine, "after_cursor_execute", listener)
        self.assertTrue(fired[0])
        self.assertEqual(raised.exception.code, REPAIR_ACTIVE_OPERATION)
        self.assertFalse(
            any("FROM documents" in statement for statement in statements)
        )

    def test_i04_preparation_insert_after_first_statement_is_visible(self) -> None:
        contract = self._contract()
        statements: list[str] = []
        listener, fired = self._after_current_database_listener(
            lambda: self._commit_preparation_insert("i04"),
            statements,
        )
        event.listen(engine, "after_cursor_execute", listener)
        try:
            with self.assertRaises(DocumentMetadataRepairError) as raised:
                self._execute(contract=contract, execute=True)
        finally:
            event.remove(engine, "after_cursor_execute", listener)
        self.assertTrue(fired[0])
        self.assertEqual(raised.exception.code, REPAIR_TARGET_ACTIVE)
        self.assertFalse(
            any(statement.startswith("UPDATE documents") for statement in statements)
        )

    def test_i05_terminal_preparation_reactivation_is_visible(self) -> None:
        self._seed_preparation_job(status="ready", generation="i05-ready")
        contract = self._contract()
        statements: list[str] = []

        def reactivate() -> None:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE document_preparation_jobs "
                        "SET status='queued', stage='queued' WHERE id=:id"
                    ),
                    {"id": "doc04a1-i05-ready"},
                )

        listener, fired = self._after_current_database_listener(
            reactivate,
            statements,
        )
        event.listen(engine, "after_cursor_execute", listener)
        try:
            with self.assertRaises(DocumentMetadataRepairError) as raised:
                self._execute(contract=contract, execute=True)
        finally:
            event.remove(engine, "after_cursor_execute", listener)
        self.assertTrue(fired[0])
        self.assertEqual(raised.exception.code, REPAIR_TARGET_ACTIVE)

    def test_i06_document_status_commit_before_lock_is_visible(self) -> None:
        contract = self._contract()
        statements: list[str] = []

        def change_status() -> None:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE documents SET processing_status='pending' "
                        "WHERE id=:id"
                    ),
                    {"id": TARGET_ID},
                )

        listener, fired = self._after_current_database_listener(
            change_status,
            statements,
        )
        event.listen(engine, "after_cursor_execute", listener)
        try:
            with self.assertRaises(DocumentMetadataRepairError) as raised:
                self._execute(contract=contract, execute=True)
        finally:
            event.remove(engine, "after_cursor_execute", listener)
        self.assertTrue(fired[0])
        self.assertEqual(raised.exception.code, REPAIR_TARGET_ACTIVE)

    def test_i07_operation_after_repair_lock_remains_blocked(self) -> None:
        with engine.connect() as repair, engine.connect() as operation:
            repair_transaction = repair.begin()
            operation_transaction = operation.begin()
            try:
                _acquire_backup_restore_operation_lock(repair)
                acquired = operation.execute(
                    text("SELECT pg_try_advisory_xact_lock(:key)"),
                    {"key": OPERATION_LOCK_KEY},
                ).scalar_one()
                self.assertFalse(acquired)
            finally:
                operation_transaction.rollback()
                repair_transaction.rollback()

    def test_i08_insert_after_document_lock_remains_blocked(self) -> None:
        with engine.connect() as repair, engine.connect() as contender:
            repair_transaction = repair.begin()
            contender_transaction = contender.begin()
            try:
                repair.execute(
                    text("SELECT id FROM documents WHERE id=:id FOR UPDATE"),
                    {"id": TARGET_ID},
                ).one()
                contender.execute(text("SET LOCAL lock_timeout='200ms'"))
                with self.assertRaises(OperationalError):
                    contender.execute(
                        text(
                            "INSERT INTO document_preparation_jobs ("
                            "id, document_id, input_checksum, "
                            "processor_generation, trigger, priority, "
                            "status, stage, attempt_count, max_attempts"
                            ") VALUES ("
                            "'doc04a3-i08', :document_id, :checksum, "
                            "'i08', 'operator_retry', 2, 'queued', "
                            "'queued', 0, 3)"
                        ),
                        {
                            "document_id": TARGET_ID,
                            "checksum": _sha256(FILE_CONTENT),
                        },
                    )
            finally:
                contender_transaction.rollback()
                repair_transaction.rollback()

    def test_i09_update_after_preparation_share_lock_remains_blocked(self) -> None:
        self._seed_preparation_job(status="ready", generation="i09-ready")
        with engine.connect() as repair, engine.connect() as contender:
            repair_transaction = repair.begin()
            contender_transaction = contender.begin()
            try:
                row = repair.execute(
                    text(
                        "SELECT processing_status, metadata_status, "
                        "trashed_at, purged_at FROM documents "
                        "WHERE id=:id FOR UPDATE"
                    ),
                    {"id": TARGET_ID},
                ).mappings().one()
                _assert_target_quiescent(repair, dict(row))
                contender.execute(text("SET LOCAL lock_timeout='200ms'"))
                with self.assertRaises(OperationalError):
                    contender.execute(
                        text(
                            "UPDATE document_preparation_jobs "
                            "SET status='queued', stage='queued' WHERE id=:id"
                        ),
                        {"id": "doc04a1-i09-ready"},
                    )
            finally:
                contender_transaction.rollback()
                repair_transaction.rollback()

    def test_i10_final_revalidation_sees_concurrent_scope_change(self) -> None:
        self._seed_document(
            document_id=OTHER_ID,
            raw_text=SAFE_FIXTURE,
            normalized_text=SAFE_FIXTURE,
        )
        before = self._state()
        original = repair_module._scope_scan
        calls = 0

        def introduce_drift(connection):
            nonlocal calls
            result = original(connection)
            calls += 1
            if calls == 1:
                with engine.begin() as contender:
                    contender.execute(
                        text(
                            "UPDATE documents SET metadata_raw=CAST(:raw AS json) "
                            "WHERE id=:id"
                        ),
                        {"raw": RAW_FIXTURE, "id": OTHER_ID},
                    )
            return result

        with patch.object(
            repair_module,
            "_scope_scan",
            side_effect=introduce_drift,
        ):
            with self.assertRaises(DocumentMetadataRepairError) as raised:
                self._execute(execute=True)
        self.assertEqual(raised.exception.code, REPAIR_POSTCONDITION)
        self.assertEqual(self._state(), before)

    def test_i11_preflight_rejects_fresh_scope_drift(self) -> None:
        self._seed_document(
            document_id=OTHER_ID,
            raw_text=SAFE_FIXTURE,
            normalized_text=SAFE_FIXTURE,
        )
        before = self._state()
        original = repair_module._scope_scan
        calls = 0

        def introduce_drift(connection):
            nonlocal calls
            calls += 1
            result = original(connection)
            if calls == 1:
                with engine.begin() as contender:
                    contender.execute(
                        text(
                            "UPDATE documents SET metadata_raw=CAST(:raw AS json) "
                            "WHERE id=:id"
                        ),
                        {"raw": RAW_FIXTURE, "id": OTHER_ID},
                    )
            return result

        with patch.object(
            repair_module,
            "_scope_scan",
            side_effect=introduce_drift,
        ):
            with self.assertRaises(DocumentMetadataRepairError) as raised:
                self._execute(
                    execute=False,
                    production_preflight=True,
                )
        self.assertEqual(raised.exception.code, REPAIR_SCOPE)
        self.assertEqual(self._state(), before)
        self.assertEqual(calls, 2)

    def test_i12_serializable_parent_controls_expose_old_snapshot(self) -> None:
        def run_control(action) -> str:
            contract = self._contract()
            statements: list[str] = []
            listener, _fired = self._after_current_database_listener(
                action,
                statements,
            )
            event.listen(engine, "after_cursor_execute", listener)
            try:
                with patch.object(
                    repair_module,
                    "REPAIR_TRANSACTION_ISOLATION",
                    "SERIALIZABLE",
                ):
                    try:
                        result = self._execute(
                            contract=contract,
                            execute=True,
                        )
                        return result.code
                    except DocumentMetadataRepairError as error:
                        return error.code
                    except OperationalError:
                        return "POSTGRES_SERIALIZATION_FAILURE"
            finally:
                event.remove(engine, "after_cursor_execute", listener)

        backup_outcome = run_control(
            lambda: self._commit_running_backup("i12-backup")
        )
        self.assertEqual(
            backup_outcome,
            "DOCUMENT_METADATA_REPAIR_EXECUTED",
        )

        self._cleanup_operation_fixtures()
        self._cleanup_documents()
        self._seed_document()
        insert_outcome = run_control(
            lambda: self._commit_preparation_insert("i12-insert")
        )
        self.assertEqual(
            insert_outcome,
            "DOCUMENT_METADATA_REPAIR_EXECUTED",
        )

        self._cleanup_documents()
        self._seed_document()
        self._seed_preparation_job(status="ready", generation="i12-ready")

        def reactivate() -> None:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE document_preparation_jobs "
                        "SET status='queued', stage='queued' WHERE id=:id"
                    ),
                    {"id": "doc04a1-i12-ready"},
                )

        reactivation_outcome = run_control(reactivate)
        self.assertNotEqual(reactivation_outcome, REPAIR_TARGET_ACTIVE)
        self.assertIn(
            reactivation_outcome,
            {
                "DOCUMENT_METADATA_REPAIR_EXECUTED",
                "POSTGRES_SERIALIZATION_FAILURE",
            },
        )

    @staticmethod
    def _production_contract(**changes: object) -> RepairContract:
        return _guard_contract(**changes)


if __name__ == "__main__":
    unittest.main()
