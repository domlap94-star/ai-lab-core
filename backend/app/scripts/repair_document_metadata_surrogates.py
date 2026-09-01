from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.services.document_metadata_unicode_safety import (
    DOCUMENT_METADATA_REPAIR_CONTRACT_MISMATCH,
    DocumentMetadataSafetyError,
    JsonLexicalRepairResult,
    repair_json_text_surrogates,
)


TARGET_DOCUMENT_ID = 8903
APPROVED_RAW_BEFORE_SHA256 = (
    "c005357d385df268407ca49ecbea6e78e1d1620d4dbbb7cf462f3c051b649aea"
)
APPROVED_RAW_CANDIDATE_SHA256 = (
    "678d488f7380404fce8d0e8454af723b7d4efaf89a502a4d62c6a8db102642ef"
)
APPROVED_NORMALIZED_BEFORE_SHA256 = (
    "b77df8ec47441c963a4812843a768f814ea3ba01e30f3bc627c314f663761420"
)
APPROVED_NORMALIZED_CANDIDATE_SHA256 = (
    "c716b9d801e271a385b05c188b64518698ef5c264035d0261a7a4e838ad7136c"
)

REPAIR_REFUSED = "DOCUMENT_METADATA_REPAIR_REFUSED"
REPAIR_PRODUCTION_GUARD = "DOCUMENT_METADATA_REPAIR_PRODUCTION_GUARD"
REPAIR_DATABASE_MISMATCH = "DOCUMENT_METADATA_REPAIR_DATABASE_MISMATCH"
REPAIR_ALEMBIC_MISMATCH = "DOCUMENT_METADATA_REPAIR_ALEMBIC_MISMATCH"
REPAIR_BACKUP_INVALID = "DOCUMENT_METADATA_REPAIR_BACKUP_INVALID"
REPAIR_ACTIVE_OPERATION = "DOCUMENT_METADATA_REPAIR_ACTIVE_OPERATION"
REPAIR_TARGET_MISSING = "DOCUMENT_METADATA_REPAIR_TARGET_MISSING"
REPAIR_NULL_SHAPE = "DOCUMENT_METADATA_REPAIR_NULL_SHAPE"
REPAIR_BEFORE_HASH = "DOCUMENT_METADATA_REPAIR_BEFORE_HASH"
REPAIR_CANDIDATE_HASH = "DOCUMENT_METADATA_REPAIR_CANDIDATE_HASH"
REPAIR_CONCURRENCY = "DOCUMENT_METADATA_REPAIR_CONCURRENCY"
REPAIR_STORAGE = "DOCUMENT_METADATA_REPAIR_STORAGE"
REPAIR_SCOPE = "DOCUMENT_METADATA_REPAIR_SCOPE"
REPAIR_ROW_COUNT = "DOCUMENT_METADATA_REPAIR_ROW_COUNT"
REPAIR_POSTCONDITION = "DOCUMENT_METADATA_REPAIR_POSTCONDITION"

_HEX64 = frozenset("0123456789abcdef")
_MAX_SCOPE_DOCUMENTS = 100_000
_MAX_METADATA_TEXT_CHARS = 16 * 1024 * 1024


class DocumentMetadataRepairError(RuntimeError):
    """Bounded refusal with no customer or bound-parameter content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class RepairContract:
    expected_database: str
    expected_alembic_head: str
    expected_xmin: str
    expected_updated_at: datetime
    expected_storage_sha256: str
    expected_raw_before_sha256: str
    expected_raw_candidate_sha256: str
    expected_normalized_before_sha256: str
    expected_normalized_candidate_sha256: str
    expected_git_sha: str | None = None
    allow_production_ai_lab: bool = False
    owner_approval_id: str | None = None
    verified_backup_run_id: int | None = None
    verified_backup_manifest_sha256: str | None = None


@dataclass(frozen=True)
class RepairResult:
    code: str
    database: str
    executed: bool
    raw: dict[str, Any]
    normalized: dict[str, Any]
    affected_documents: int
    affected_columns: tuple[str, ...]
    backup_run_id: int | None = None
    backup_manifest_sha256: str | None = None

    def safe_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "result": self.code,
            "database": self.database,
            "document_id": TARGET_DOCUMENT_ID,
            "executed": self.executed,
            "affected_documents": self.affected_documents,
            "affected_columns": list(self.affected_columns),
            "metadata_raw": self.raw,
            "metadata_normalized": self.normalized,
        }
        if self.backup_run_id is not None:
            payload["backup_run_id"] = self.backup_run_id
        if self.backup_manifest_sha256 is not None:
            payload["backup_manifest_sha256"] = (
                self.backup_manifest_sha256
            )
        return payload


def _is_sha256(value: str | None) -> bool:
    return bool(
        value
        and len(value) == 64
        and all(char in _HEX64 for char in value)
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_git_sha() -> str:
    configured = os.environ.get(
        "NEXT_STABIL_RUNTIME_GIT_SHA", ""
    ).strip()
    if configured:
        return configured
    try:
        repository = Path(__file__).resolve().parents[3]
        process = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return process.stdout.strip()
    except Exception as error:
        raise DocumentMetadataRepairError(
            REPAIR_PRODUCTION_GUARD
        ) from error


def _relation_counts(connection: Connection) -> dict[str, int]:
    statements = {
        "parents": "SELECT count(*) FROM documents WHERE id = "
        "(SELECT parent_document_id FROM documents WHERE id=:id)",
        "children": "SELECT count(*) FROM documents WHERE parent_document_id=:id",
        "pages": "SELECT count(*) FROM document_pages WHERE document_id=:id",
        "assets": "SELECT count(*) FROM document_assets WHERE document_id=:id",
        "chunks": "SELECT count(*) FROM document_chunks WHERE document_id=:id",
        "preparation": "SELECT count(*) FROM document_preparation_jobs WHERE document_id=:id",
        "intelligence": "SELECT count(*) FROM document_intelligence_artifacts WHERE document_id=:id",
    }
    return {
        name: int(
            connection.execute(
                text(statement), {"id": TARGET_DOCUMENT_ID}
            ).scalar_one()
        )
        for name, statement in statements.items()
    }


def _validate_production_gate(
    connection: Connection,
    *,
    database: str,
    execute: bool,
    contract: RepairContract,
) -> None:
    if database != "ai_lab":
        return
    required = (
        execute,
        contract.allow_production_ai_lab,
        bool(contract.owner_approval_id),
        bool(contract.expected_git_sha),
        bool(contract.expected_alembic_head),
        bool(contract.expected_xmin),
        isinstance(contract.expected_updated_at, datetime),
        _is_sha256(contract.expected_storage_sha256),
        contract.verified_backup_run_id is not None,
        _is_sha256(contract.verified_backup_manifest_sha256),
        _is_sha256(contract.expected_raw_before_sha256),
        _is_sha256(contract.expected_raw_candidate_sha256),
        _is_sha256(contract.expected_normalized_before_sha256),
        _is_sha256(contract.expected_normalized_candidate_sha256),
    )
    if not all(required):
        raise DocumentMetadataRepairError(
            REPAIR_PRODUCTION_GUARD
        )
    if (
        contract.expected_raw_before_sha256
        != APPROVED_RAW_BEFORE_SHA256
        or contract.expected_raw_candidate_sha256
        != APPROVED_RAW_CANDIDATE_SHA256
        or contract.expected_normalized_before_sha256
        != APPROVED_NORMALIZED_BEFORE_SHA256
        or contract.expected_normalized_candidate_sha256
        != APPROVED_NORMALIZED_CANDIDATE_SHA256
    ):
        raise DocumentMetadataRepairError(
            REPAIR_PRODUCTION_GUARD
        )
    if _runtime_git_sha() != contract.expected_git_sha:
        raise DocumentMetadataRepairError(
            REPAIR_PRODUCTION_GUARD
        )

    backup = connection.execute(
        text(
            "SELECT br.status, br.verified, mb.manifest_sha256, "
            "mb.integrity_status, mb.lifecycle "
            "FROM backup_runs br "
            "JOIN managed_backups mb ON mb.backup_run_id=br.id "
            "WHERE br.id=:backup_run_id"
        ),
        {"backup_run_id": contract.verified_backup_run_id},
    ).mappings().one_or_none()
    if (
        backup is None
        or backup["status"] != "completed"
        or backup["verified"] is not True
        or backup["integrity_status"] != "verified"
        or backup["lifecycle"] != "available"
        or str(backup["manifest_sha256"]).lower()
        != contract.verified_backup_manifest_sha256
    ):
        raise DocumentMetadataRepairError(
            REPAIR_BACKUP_INVALID
        )


def _assert_no_active_operations(connection: Connection) -> None:
    backup_count = int(
        connection.execute(
            text(
                "SELECT count(*) FROM backup_runs "
                "WHERE status IN ('queued','running')"
            )
        ).scalar_one()
    )
    restore_count = int(
        connection.execute(
            text(
                "SELECT count(*) FROM restore_runs "
                "WHERE status IN ('queued','running')"
            )
        ).scalar_one()
    )
    if backup_count or restore_count:
        raise DocumentMetadataRepairError(
            REPAIR_ACTIVE_OPERATION
        )


def _scope_scan(connection: Connection) -> tuple[int, tuple[str, ...]]:
    affected: dict[int, list[str]] = {}
    document_count = 0
    statement = text(
        "SELECT id, metadata_raw::text, metadata_normalized::text "
        "FROM documents ORDER BY id"
    ).execution_options(
        stream_results=True,
        max_row_buffer=100,
    )
    result = connection.execute(statement)
    for row in result.mappings():
        document_count += 1
        if document_count > _MAX_SCOPE_DOCUMENTS:
            raise DocumentMetadataRepairError(REPAIR_SCOPE)
        for column in ("metadata_raw", "metadata_normalized"):
            value = row[column]
            if value is None:
                continue
            if len(value) > _MAX_METADATA_TEXT_CHARS:
                raise DocumentMetadataRepairError(REPAIR_SCOPE)
            repaired = repair_json_text_surrogates(value)
            if repaired.replacement_count:
                affected.setdefault(int(row["id"]), []).append(column)
    if set(affected) != {TARGET_DOCUMENT_ID}:
        raise DocumentMetadataRepairError(REPAIR_SCOPE)
    columns = tuple(sorted(affected[TARGET_DOCUMENT_ID]))
    if columns != ("metadata_normalized", "metadata_raw"):
        raise DocumentMetadataRepairError(REPAIR_SCOPE)
    return len(affected), columns


def _assert_candidate(
    result: JsonLexicalRepairResult,
    *,
    before_sha256: str,
    candidate_sha256: str,
) -> None:
    if result.before_sha256 != before_sha256:
        raise DocumentMetadataRepairError(REPAIR_BEFORE_HASH)
    if result.after_sha256 != candidate_sha256:
        raise DocumentMetadataRepairError(REPAIR_CANDIDATE_HASH)
    if not result.replacement_count:
        raise DocumentMetadataRepairError(
            DOCUMENT_METADATA_REPAIR_CONTRACT_MISMATCH
        )


def execute_repair(
    connection: Connection,
    *,
    contract: RepairContract,
    data_root: Path,
    execute: bool = False,
) -> RepairResult:
    if connection.in_transaction():
        raise DocumentMetadataRepairError(REPAIR_REFUSED)
    connection = connection.execution_options(
        isolation_level="SERIALIZABLE"
    )
    transaction = connection.begin()
    committed = False
    try:
        database = str(
            connection.execute(
                text("SELECT current_database()")
            ).scalar_one()
        )
        if database != contract.expected_database:
            raise DocumentMetadataRepairError(
                REPAIR_DATABASE_MISMATCH
            )
        _validate_production_gate(
            connection,
            database=database,
            execute=execute,
            contract=contract,
        )
        db_head = str(
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        )
        if db_head != contract.expected_alembic_head:
            raise DocumentMetadataRepairError(
                REPAIR_ALEMBIC_MISMATCH
            )
        _assert_no_active_operations(connection)

        row = connection.execute(
            text(
                "SELECT id, xmin::text AS xmin, updated_at, "
                "metadata_raw IS NULL AS raw_is_null, "
                "metadata_normalized IS NULL AS normalized_is_null, "
                "metadata_raw::text AS metadata_raw, "
                "metadata_normalized::text AS metadata_normalized, "
                "storage_path, file_size, checksum_sha256 "
                "FROM documents WHERE id=:id FOR UPDATE"
            ),
            {"id": TARGET_DOCUMENT_ID},
        ).mappings().one_or_none()
        if row is None:
            raise DocumentMetadataRepairError(
                REPAIR_TARGET_MISSING
            )
        if row["raw_is_null"] or row["normalized_is_null"]:
            raise DocumentMetadataRepairError(REPAIR_NULL_SHAPE)
        if (
            str(row["xmin"]) != contract.expected_xmin
            or row["updated_at"] != contract.expected_updated_at
        ):
            raise DocumentMetadataRepairError(REPAIR_CONCURRENCY)

        try:
            trusted_root = data_root.resolve(strict=True)
            source = (
                trusted_root / str(row["storage_path"])
            ).resolve(strict=True)
            source.relative_to(trusted_root)
        except (OSError, ValueError) as error:
            raise DocumentMetadataRepairError(REPAIR_STORAGE) from error
        if not source.is_file():
            raise DocumentMetadataRepairError(REPAIR_STORAGE)
        actual_size = source.stat().st_size
        actual_storage_sha = _sha256_file(source)
        if (
            actual_size != int(row["file_size"])
            or actual_storage_sha
            != str(row["checksum_sha256"] or "").lower()
            or actual_storage_sha
            != contract.expected_storage_sha256
        ):
            raise DocumentMetadataRepairError(REPAIR_STORAGE)

        relations_before = _relation_counts(connection)
        raw_text = str(row["metadata_raw"])
        normalized_text = str(row["metadata_normalized"])
        if (
            hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            != contract.expected_raw_before_sha256
            or hashlib.sha256(
                normalized_text.encode("utf-8")
            ).hexdigest()
            != contract.expected_normalized_before_sha256
        ):
            raise DocumentMetadataRepairError(REPAIR_BEFORE_HASH)
        affected_count, affected_columns = _scope_scan(connection)
        raw_result = repair_json_text_surrogates(raw_text)
        normalized_result = repair_json_text_surrogates(normalized_text)
        _assert_candidate(
            raw_result,
            before_sha256=contract.expected_raw_before_sha256,
            candidate_sha256=contract.expected_raw_candidate_sha256,
        )
        _assert_candidate(
            normalized_result,
            before_sha256=contract.expected_normalized_before_sha256,
            candidate_sha256=(
                contract.expected_normalized_candidate_sha256
            ),
        )

        if execute:
            updated = connection.execute(
                text(
                    "UPDATE documents SET "
                    "metadata_raw=CAST(:candidate_raw AS json), "
                    "metadata_normalized=CAST(:candidate_normalized AS json) "
                    "WHERE id=:id AND xmin::text=:expected_xmin "
                    "AND updated_at=:expected_updated_at "
                    "AND metadata_raw IS NOT NULL "
                    "AND metadata_normalized IS NOT NULL "
                    "AND metadata_raw::text=:expected_raw "
                    "AND metadata_normalized::text=:expected_normalized"
                ),
                {
                    "candidate_raw": raw_result.candidate_text,
                    "candidate_normalized": (
                        normalized_result.candidate_text
                    ),
                    "id": TARGET_DOCUMENT_ID,
                    "expected_xmin": contract.expected_xmin,
                    "expected_updated_at": contract.expected_updated_at,
                    "expected_raw": row["metadata_raw"],
                    "expected_normalized": row["metadata_normalized"],
                },
            )
            if updated.rowcount != 1:
                raise DocumentMetadataRepairError(REPAIR_ROW_COUNT)

            post = connection.execute(
                text(
                    "SELECT metadata_raw::text AS metadata_raw, "
                    "metadata_normalized::text AS metadata_normalized, "
                    "jsonb_typeof(metadata_raw::jsonb) AS raw_type, "
                    "jsonb_typeof(metadata_normalized::jsonb) AS normalized_type, "
                    "(metadata_raw -> '__doc04a_probe__') IS NULL "
                    "AS raw_operator_ok, "
                    "(metadata_normalized -> '__doc04a_probe__') IS NULL "
                    "AS normalized_operator_ok "
                    "FROM documents WHERE id=:id"
                ),
                {"id": TARGET_DOCUMENT_ID},
            ).mappings().one()
            post_raw = repair_json_text_surrogates(post["metadata_raw"])
            post_normalized = repair_json_text_surrogates(
                post["metadata_normalized"]
            )
            if (
                post_raw.before_sha256
                != contract.expected_raw_candidate_sha256
                or post_normalized.before_sha256
                != contract.expected_normalized_candidate_sha256
                or post_raw.replacement_count
                or post_normalized.replacement_count
                or post["raw_type"] != raw_result.top_level_type
                or post["normalized_type"]
                != normalized_result.top_level_type
                or not post["raw_operator_ok"]
                or not post["normalized_operator_ok"]
            ):
                raise DocumentMetadataRepairError(REPAIR_POSTCONDITION)

            session = Session(
                bind=connection,
                autoflush=False,
                join_transaction_mode="create_savepoint",
            )
            try:
                if session.get(Document, TARGET_DOCUMENT_ID) is None:
                    raise DocumentMetadataRepairError(
                        REPAIR_POSTCONDITION
                    )
            finally:
                session.close()

            if (
                _relation_counts(connection) != relations_before
                or source.stat().st_size != actual_size
                or _sha256_file(source) != actual_storage_sha
            ):
                raise DocumentMetadataRepairError(REPAIR_POSTCONDITION)
            remaining = connection.execute(
                text(
                    "SELECT metadata_raw::text, metadata_normalized::text "
                    "FROM documents WHERE id<>:id ORDER BY id"
                ),
                {"id": TARGET_DOCUMENT_ID},
            )
            for other_raw, other_normalized in remaining:
                for other in (other_raw, other_normalized):
                    if (
                        other is not None
                        and repair_json_text_surrogates(
                            other
                        ).replacement_count
                    ):
                        raise DocumentMetadataRepairError(
                            REPAIR_POSTCONDITION
                        )
            transaction.commit()
            committed = True
        else:
            transaction.rollback()

        return RepairResult(
            code=("DOCUMENT_METADATA_REPAIR_EXECUTED" if execute else "DOCUMENT_METADATA_REPAIR_DRY_RUN"),
            database=database,
            executed=execute,
            raw=raw_result.safe_evidence(),
            normalized=normalized_result.safe_evidence(),
            affected_documents=affected_count,
            affected_columns=affected_columns,
            backup_run_id=(
                contract.verified_backup_run_id
                if database == "ai_lab"
                else None
            ),
            backup_manifest_sha256=(
                contract.verified_backup_manifest_sha256
                if database == "ai_lab"
                else None
            ),
        )
    except Exception:
        if transaction.is_active:
            transaction.rollback()
        raise
    finally:
        if not committed and connection.in_transaction():
            connection.rollback()


def _required(value: str | None) -> str:
    if not value:
        raise DocumentMetadataRepairError(REPAIR_REFUSED)
    return value


def _parse_datetime(value: str | None) -> datetime:
    try:
        return datetime.fromisoformat(_required(value))
    except DocumentMetadataRepairError:
        raise
    except Exception as error:
        raise DocumentMetadataRepairError(REPAIR_REFUSED) from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Guarded one-row document metadata surrogate repair."
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--allow-production-ai-lab", action="store_true"
    )
    parser.add_argument("--owner-approval-id")
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--expected-git-sha")
    parser.add_argument("--expected-alembic-head", required=True)
    parser.add_argument("--expected-xmin", required=True)
    parser.add_argument("--expected-updated-at", required=True)
    parser.add_argument("--expected-storage-sha256", required=True)
    parser.add_argument("--verified-backup-run-id", type=int)
    parser.add_argument("--verified-backup-manifest-sha256")
    parser.add_argument("--expected-raw-before-sha256", required=True)
    parser.add_argument("--expected-raw-candidate-sha256", required=True)
    parser.add_argument(
        "--expected-normalized-before-sha256", required=True
    )
    parser.add_argument(
        "--expected-normalized-candidate-sha256", required=True
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        contract = RepairContract(
            expected_database=args.expected_database,
            expected_git_sha=args.expected_git_sha,
            expected_alembic_head=args.expected_alembic_head,
            expected_xmin=args.expected_xmin,
            expected_updated_at=_parse_datetime(
                args.expected_updated_at
            ),
            expected_storage_sha256=(
                args.expected_storage_sha256.lower()
            ),
            expected_raw_before_sha256=(
                args.expected_raw_before_sha256.lower()
            ),
            expected_raw_candidate_sha256=(
                args.expected_raw_candidate_sha256.lower()
            ),
            expected_normalized_before_sha256=(
                args.expected_normalized_before_sha256.lower()
            ),
            expected_normalized_candidate_sha256=(
                args.expected_normalized_candidate_sha256.lower()
            ),
            allow_production_ai_lab=args.allow_production_ai_lab,
            owner_approval_id=args.owner_approval_id,
            verified_backup_run_id=args.verified_backup_run_id,
            verified_backup_manifest_sha256=(
                args.verified_backup_manifest_sha256.lower()
                if args.verified_backup_manifest_sha256
                else None
            ),
        )
        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
        try:
            with engine.connect() as connection:
                result = execute_repair(
                    connection,
                    contract=contract,
                    data_root=Path(settings.data_dir),
                    execute=args.execute,
                )
            print(
                json.dumps(
                    result.safe_payload(),
                    ensure_ascii=True,
                    sort_keys=True,
                )
            )
            return 0
        finally:
            engine.dispose()
    except (DocumentMetadataRepairError, DocumentMetadataSafetyError) as error:
        code = getattr(error, "code", REPAIR_REFUSED)
        print(
            json.dumps(
                {"result": code, "executed": False},
                sort_keys=True,
            )
        )
        return 2
    except Exception:
        print(
            json.dumps(
                {"result": REPAIR_REFUSED, "executed": False},
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
