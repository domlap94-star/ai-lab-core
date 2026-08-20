from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy import inspect, text

from app.database.session import SessionLocal
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate
from app.services.client_added_date_projection_service import (
    ClientAddedDateProjectionService,
)
from app.services.client_service import ClientService


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "followup_clientdate_20260819_add_client_added_date.py"
)
ISOLATED_DB_NAME = "ai_lab_chunk03_isolated"


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "followup_clientdate_20260819",
        MIGRATION_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Client added date migration could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ClientAddedDateContractTests(unittest.TestCase):
    def test_migration_is_additive_only(self) -> None:
        migration = _load_migration()
        operations = MagicMock()

        with patch.object(migration, "op", operations):
            migration.upgrade()

        self.assertEqual(migration.revision, "followup_clientdate_20260819")
        self.assertEqual(migration.down_revision, "chunk16audit_20260819")
        operations.add_column.assert_called_once()
        table_name, column = operations.add_column.call_args.args
        self.assertEqual(table_name, "clients")
        self.assertEqual(column.name, "client_added_at")
        self.assertTrue(column.nullable)
        self.assertIsNone(column.server_default)
        operations.execute.assert_not_called()
        operations.create_index.assert_not_called()
        operations.create_table.assert_not_called()

    def test_downgrade_drops_only_the_new_column(self) -> None:
        migration = _load_migration()
        operations = MagicMock()

        with patch.object(migration, "op", operations):
            migration.downgrade()

        operations.drop_column.assert_called_once_with(
            "clients",
            "client_added_at",
        )
        operations.execute.assert_not_called()
        operations.drop_table.assert_not_called()

    def test_validation_accepts_set_and_clear_and_rejects_bounds(self) -> None:
        accepted = ClientUpdate(client_added_at=date(2026, 8, 19))
        self.assertEqual(accepted.client_added_at, date(2026, 8, 19))
        cleared = ClientUpdate.model_validate({"client_added_at": None})
        self.assertIn("client_added_at", cleared.model_fields_set)
        self.assertIsNone(cleared.client_added_at)

        with self.assertRaises(ValidationError):
            ClientUpdate(client_added_at=date(1899, 12, 31))
        with self.assertRaises(ValidationError):
            ClientUpdate(client_added_at=date.today() + timedelta(days=1))

    def test_projection_and_ordering_cover_all_fallbacks(self) -> None:
        created = datetime(2026, 8, 10, tzinfo=timezone.utc)
        candidates = [
            (101, created, date(2020, 1, 1)),
            (102, created, date(2025, 1, 1)),
            (103, created, None),
            (104, datetime(2024, 1, 1, tzinfo=timezone.utc), None),
            (105, created, date(2025, 1, 1)),
        ]
        source_dates = {103: date(2023, 1, 1)}

        newest = ClientAddedDateProjectionService.order_client_ids(
            candidates,
            source_dates,
            sort_order="newest",
        )
        oldest = ClientAddedDateProjectionService.order_client_ids(
            candidates,
            source_dates,
            sort_order="oldest",
        )

        self.assertEqual(newest, [105, 102, 104, 103, 101])
        self.assertEqual(oldest, [101, 103, 104, 102, 105])
        self.assertEqual(newest[:2], [105, 102])
        self.assertEqual(newest[2:4], [104, 103])
        self.assertEqual(len(set(newest[:2]) & set(newest[2:4])), 0)


@unittest.skipUnless(
    os.getenv("POSTGRES_DB") == ISOLATED_DB_NAME,
    "requires the explicitly isolated CHUNK 03 database",
)
class ClientAddedDateIsolatedDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.query(Client).filter(
            Client.name.like("CHUNK03 %")
        ).delete(synchronize_session=False)
        self.db.commit()
        self.db.close()

    def test_schema_history_and_service_set_clear_are_safe(self) -> None:
        current_revision = self.db.execute(
            text("select version_num from alembic_version")
        ).scalar_one()
        script = ScriptDirectory.from_config(Config("/app/alembic.ini"))
        lineage = {
            revision.revision
            for revision in script.iterate_revisions(current_revision, "base")
        }
        self.assertIn("followup_clientdate_20260819", lineage)
        column = next(
            item
            for item in inspect(self.db.bind).get_columns("clients")
            if item["name"] == "client_added_at"
        )
        self.assertTrue(column["nullable"])
        self.assertIsNone(column["default"])
        self.assertEqual(
            self.db.execute(
                text(
                    "select count(1) from clients "
                    "where client_added_at is not null "
                    "and name not like 'CHUNK03 %'"
                )
            ).scalar(),
            0,
        )

        client = Client(
            client_type="other",
            name="CHUNK03 isolated fixture",
            country_code="PL",
        )
        self.db.add(client)
        self.db.commit()
        client_id = client.id
        service = ClientService(self.db)
        original = service.get_client(client_id)
        created_at = original.created_at
        source_record_date = original.source_record_date
        workflow_effective_date = original.workflow_effective_date

        explicit = service.update_client(
            client_id,
            ClientUpdate(client_added_at=date(2020, 5, 6)),
        )
        self.assertEqual(explicit.client_added_at, date(2020, 5, 6))
        self.assertEqual(explicit.effective_added_date, date(2020, 5, 6))
        self.assertEqual(explicit.created_at, created_at)
        self.assertEqual(explicit.source_record_date, source_record_date)
        self.assertEqual(explicit.workflow_effective_date, workflow_effective_date)

        cleared = service.update_client(
            client_id,
            ClientUpdate.model_validate({"client_added_at": None}),
        )
        self.assertIsNone(cleared.client_added_at)
        self.assertEqual(cleared.effective_added_date, created_at.date())
        self.assertEqual(cleared.created_at, created_at)
        self.assertEqual(cleared.source_record_date, source_record_date)
        self.assertEqual(cleared.workflow_effective_date, workflow_effective_date)

    def test_filtered_sorting_is_backend_side_and_paginated(self) -> None:
        prefix = "CHUNK03 sort fixture"
        fixtures = [
            Client(
                client_type="other",
                name=f"{prefix} {suffix}",
                country_code="PL",
                client_added_at=added,
            )
            for suffix, added in (
                ("A", date(2020, 1, 1)),
                ("B", date(2025, 1, 1)),
                ("C", date(2025, 1, 1)),
                ("D", date(2022, 1, 1)),
                ("E", date(2023, 1, 1)),
            )
        ]
        self.db.add_all(fixtures)
        self.db.commit()
        service = ClientService(self.db)

        newest_first = service.get_clients(
            search=prefix,
            sort_order="newest",
            skip=0,
            limit=2,
        )
        newest_second = service.get_clients(
            search=prefix,
            sort_order="newest",
            skip=2,
            limit=2,
        )
        oldest = service.get_clients(
            search=prefix,
            sort_order="oldest",
            skip=0,
            limit=5,
        )

        self.assertEqual(newest_first.total, 5)
        self.assertEqual(
            [item.id for item in newest_first.items],
            sorted([fixtures[1].id, fixtures[2].id], reverse=True),
        )
        self.assertFalse(
            {item.id for item in newest_first.items}
            & {item.id for item in newest_second.items}
        )
        self.assertEqual(
            [item.effective_added_date for item in oldest.items],
            sorted(item.client_added_at for item in fixtures),
        )


if __name__ == "__main__":
    unittest.main()
