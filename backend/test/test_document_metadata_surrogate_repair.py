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

from sqlalchemy import text

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
    REPAIR_POSTCONDITION,
    REPAIR_PRODUCTION_GUARD,
    REPAIR_RUNTIME_SOURCE_MISMATCH,
    REPAIR_SCOPE,
    REPAIR_STORAGE,
    REPAIR_TARGET_MISSING,
    REPAIR_TARGET_ACTIVE,
    BackupEvidence,
    DocumentMetadataRepairError,
    RepairContract,
    RepairResult,
    _assert_no_active_operations,
    _assert_target_quiescent,
    _backup_root_sha256,
    _parser,
    _revalidate_production_guards,
    _validate_backup_evidence,
    _validate_production_gate,
    _verify_backup_physical,
    _verify_runtime_source_identity,
    execute_repair,
)
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
        self._cleanup_documents()
        self._seed_document()

    def tearDown(self) -> None:
        self._cleanup_documents()
        self.storage.cleanup()

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
    ) -> RepairResult:
        with engine.connect() as connection:
            return execute_repair(
                connection,
                contract=contract or self._contract(),
                data_root=self.data_root,
                execute=execute,
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
                execute=True,
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
                execute=True,
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
                execute=True,
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

    @staticmethod
    def _production_contract(**changes: object) -> RepairContract:
        return _guard_contract(**changes)


if __name__ == "__main__":
    unittest.main()
