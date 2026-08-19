from pathlib import Path
import unittest


MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "followup_mail_read_index_supersession_20260819.py"
)


class MailReadIndexSupersessionMigrationTests(unittest.TestCase):
    def test_revision_is_online_and_removes_only_legacy_index(self) -> None:
        source = MIGRATION.read_text(encoding="utf-8")
        self.assertIn(
            'revision = "followup_mail_read_index_supersession_20260819"',
            source,
        )
        self.assertIn(
            'down_revision = "followup_mail_composite_indexes_20260819"',
            source,
        )
        self.assertEqual(source.count("DROP INDEX CONCURRENTLY"), 1)
        self.assertEqual(source.count("CREATE INDEX CONCURRENTLY"), 1)
        self.assertEqual(source.count("autocommit_block()"), 2)
        self.assertIn("ix_candidate_sources_gmail_read_state", source)
        self.assertNotIn("ix_candidate_sources_gmail_read_time\"", source)

        upper = source.upper()
        for forbidden in (
            "INSERT INTO",
            "UPDATE CANDIDATE_SOURCES",
            "DELETE FROM",
            "ALTER TABLE",
            "CREATE TRIGGER",
        ):
            self.assertNotIn(forbidden, upper)

    def test_downgrade_is_exact_historical_definition(self) -> None:
        baseline = (
            MIGRATION.parent / "followup_mail_query_indexes_20260819.py"
        ).read_text(encoding="utf-8")
        source = MIGRATION.read_text(encoding="utf-8")
        for marker in (
            "json_typeof(coalesce(raw_payload -> 'labelIds'",
            "'%\"UNREAD\"%'",
            "source_type = 'gmail_message' AND deleted_at IS NULL",
        ):
            self.assertIn(marker, baseline)
            self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
