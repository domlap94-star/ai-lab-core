from pathlib import Path
import unittest


class MailSendMigrationTests(unittest.TestCase):
    def test_mail_send_migration_is_additive_and_bounded(self):
        path = Path(__file__).parents[1] / "alembic" / "versions" / "followup_mail_send_ops_20260819.py"
        text = path.read_text(encoding="utf-8")
        self.assertIn('down_revision = "followup_mail_nullable_read_state_20260819"', text)
        self.assertIn('"mail_send_operations"', text)
        self.assertIn("op.create_table", text)
        self.assertIn("op.drop_table", text)
        lowered = text.lower()
        self.assertNotIn("update ", lowered)
        self.assertNotIn("insert ", lowered)
        self.assertNotIn("backfill", lowered)


if __name__ == "__main__":
    unittest.main()
