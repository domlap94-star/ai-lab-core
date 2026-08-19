from pathlib import Path
import unittest

from app.database.global_mail_sql import GMAIL_READ_STATE_SQL


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / (
    "followup_mail_nullable_read_state_20260819.py"
)


class NullableReadStateContractTests(unittest.TestCase):
    def test_missing_and_non_array_labels_are_unknown(self) -> None:
        self.assertIn("IS NULL", GMAIL_READ_STATE_SQL)
        self.assertIn("<> 'array'", GMAIL_READ_STATE_SQL)
        self.assertIn("THEN 'unread'", GMAIL_READ_STATE_SQL)
        self.assertTrue(GMAIL_READ_STATE_SQL.rstrip().endswith("END"))

    def test_migration_is_online_and_linear(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        upgrade, downgrade = source.split("def downgrade", 1)
        self.assertIn(
            'down_revision = "followup_mail_read_index_supersession_20260819"',
            source,
        )
        self.assertIn("autocommit_block()", upgrade)
        self.assertIn("CREATE INDEX CONCURRENTLY", upgrade)
        self.assertIn(
            "DROP INDEX CONCURRENTLY IF EXISTS {PREVIOUS_INDEX}", upgrade
        )
        self.assertIn("CREATE INDEX CONCURRENTLY", downgrade)
        self.assertIn(
            "DROP INDEX CONCURRENTLY IF EXISTS {CORRECTED_INDEX}", downgrade
        )

    def test_migration_contains_no_business_dml(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8").upper()
        for forbidden in ("INSERT INTO", "UPDATE CANDIDATE_SOURCES", "DELETE FROM"):
            self.assertNotIn(forbidden, source)

    def test_runtime_and_index_import_same_expression(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("GMAIL_READ_STATE_SQL", source)
        self.assertNotIn("WHEN COALESCE(RAW_PAYLOAD", source.upper())


if __name__ == "__main__":
    unittest.main()
