from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, JSON, UniqueConstraint

from app.models.agent_execution import AgentExecution
from app.schemas.agent_audit import AgentExecutionMetadata


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "chunk16audit_20260819_add_agent_execution_audit.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "chunk16audit_20260819",
        MIGRATION_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Agent audit migration could not be loaded.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Chunk16AgentAuditMigrationTests(unittest.TestCase):
    def test_upgrade_creates_only_the_approved_table_and_indexes(self) -> None:
        migration = _load_migration()
        operations = MagicMock()

        with patch.object(migration, "op", operations):
            migration.upgrade()

        self.assertEqual(migration.revision, "chunk16audit_20260819")
        self.assertEqual(migration.down_revision, "chunk15vision_20260818")
        operations.create_table.assert_called_once()
        self.assertEqual(operations.create_table.call_args.args[0], "agent_executions")
        self.assertEqual(operations.create_index.call_count, 2)
        operations.add_column.assert_not_called()
        operations.alter_column.assert_not_called()
        operations.execute.assert_not_called()
        operations.drop_table.assert_not_called()

    def test_downgrade_removes_only_agent_audit_objects(self) -> None:
        migration = _load_migration()
        operations = MagicMock()

        with patch.object(migration, "op", operations):
            migration.downgrade()

        self.assertEqual(operations.drop_index.call_count, 2)
        operations.drop_table.assert_called_once_with("agent_executions")
        operations.execute.assert_not_called()
        operations.drop_column.assert_not_called()

    def test_orm_contract_has_unique_request_restricted_user_and_json(self) -> None:
        table = AgentExecution.__table__
        self.assertEqual(
            set(table.c),
            {
                table.c.id,
                table.c.request_id,
                table.c.user_id,
                table.c.created_at,
                table.c.completed_at,
                table.c.status,
                table.c.tool_count,
                table.c.duration_ms,
                table.c.execution_metadata,
            },
        )
        self.assertIsInstance(table.c.execution_metadata.type, JSON)
        self.assertEqual(str(table.c.tool_count.server_default.arg), "0")

        unique = [item for item in table.constraints if isinstance(item, UniqueConstraint)]
        self.assertEqual([constraint.name for constraint in unique], ["uq_agent_executions_request_id"])
        foreign_keys = [item for item in table.constraints if isinstance(item, ForeignKeyConstraint)]
        self.assertEqual(len(foreign_keys), 1)
        self.assertEqual(foreign_keys[0].referred_table.name, "users")
        self.assertEqual(foreign_keys[0].ondelete, "RESTRICT")
        self.assertEqual(
            {item.name for item in table.constraints if isinstance(item, CheckConstraint)},
            {
                "ck_agent_executions_status",
                "ck_agent_executions_tool_count_nonnegative",
                "ck_agent_executions_duration_nonnegative",
            },
        )

    def test_metadata_is_bounded_and_rejects_sensitive_content_fields(self) -> None:
        safe = AgentExecutionMetadata.model_validate(
            {
                "tools": [
                    {"name": "search_clients", "outcome": "ok", "duration_ms": 21}
                ],
                "rounds": 1,
                "final_status": "completed",
            }
        )
        self.assertEqual(safe.model_dump()["tools"][0]["name"], "search_clients")

        for forbidden in (
            "prompt",
            "raw_response",
            "token",
            "authorization",
            "document_text",
            "email_body",
            "sql",
            "stack_trace",
        ):
            with self.subTest(forbidden=forbidden), self.assertRaises(ValidationError):
                AgentExecutionMetadata.model_validate(
                    {
                        "tools": [],
                        "rounds": 0,
                        "final_status": "blocked",
                        forbidden: "secret-or-customer-content",
                    }
                )


if __name__ == "__main__":
    unittest.main()
