from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "followup_mail_composite_indexes_20260819.py"
)


class FollowupMailCompositeIndexMigrationTests(unittest.TestCase):
    def test_revision_is_linear_and_online_only(self) -> None:
        source = MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn(
            'revision = "followup_mail_composite_indexes_20260819"', source
        )
        self.assertIn(
            'down_revision = "followup_mail_query_indexes_20260819"', source
        )
        self.assertEqual(source.count("CREATE INDEX CONCURRENTLY"), 2)
        self.assertEqual(source.count("DROP INDEX CONCURRENTLY"), 2)
        self.assertIn("autocommit_block()", source)
        for forbidden in (
            "ADD COLUMN",
            "UPDATE candidate_sources",
            "INSERT INTO",
            "DELETE FROM",
            "CREATE TRIGGER",
        ):
            self.assertNotIn(forbidden, source.upper())

    def test_indexes_match_common_filter_and_time_order(self) -> None:
        source = MIGRATION_PATH.read_text(encoding="utf-8")
        self.assertIn("ix_candidate_sources_gmail_received_time", source)
        self.assertIn("ix_candidate_sources_gmail_read_time", source)
        self.assertIn("({DIRECTION_SQL}) = 'received'", source)
        self.assertIn("({READ_STATE_SQL}), ", source)
        self.assertNotIn("unknown_time", source)
        self.assertNotIn("unread_time", source)


if __name__ == "__main__":
    unittest.main()
