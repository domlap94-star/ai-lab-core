from pathlib import Path
import unittest

from pydantic import ValidationError

from app.models.client import Client
from app.schemas.client import ClientUpdate
from app.services.client_service import ClientService


class _Db:
    def flush(self):
        return None


class ClientContactModelTests(unittest.TestCase):
    def setUp(self):
        self.service = ClientService.__new__(ClientService)
        self.service.db = _Db()

    def test_married_couple_contacts_are_separate_and_primary_is_synced(self):
        data = ClientUpdate(
            emails=[
                {"value": "jan@example.com", "is_primary": True},
                {"value": "anna@example.com", "is_primary": False},
            ],
            phones=[
                {"value": "+48 500 000 001", "is_primary": False},
                {"value": "+48 500 000 002", "is_primary": True},
            ],
        )
        self.assertEqual(len(data.emails), 2)
        self.assertEqual(len(data.phones), 2)
        self.assertEqual(self.service._primary_value(data.emails), "jan@example.com")
        self.assertEqual(self.service._primary_value(data.phones), "+48 500 000 002")

    def test_duplicate_email_and_phone_are_rejected(self):
        with self.assertRaises(ValidationError):
            ClientUpdate(emails=[{"value": "A@example.com"}, {"value": "a@example.com"}])
        with self.assertRaises(ValidationError):
            ClientUpdate(phones=[{"value": "+48 500-000-001"}, {"value": "+48500000001"}])

    def test_first_contact_becomes_primary_deterministically(self):
        data = ClientUpdate(emails=[{"value": "first@example.com"}, {"value": "second@example.com"}])
        self.assertTrue(data.emails[0].is_primary)
        self.assertFalse(data.emails[1].is_primary)

    def test_omitted_contacts_remain_omitted(self):
        data = ClientUpdate(notes=None)
        self.assertNotIn("emails", data.model_dump(exclude_unset=True))
        self.assertNotIn("phones", data.model_dump(exclude_unset=True))

    def test_migration_is_additive_and_does_not_split_legacy_values(self):
        text = Path("/app/alembic/versions/contact_20260816_add_client_contact_points.py").read_text()
        self.assertIn("CREATE", text.upper())
        self.assertNotIn("split_part", text)
        self.assertNotIn("DROP COLUMN", text.upper())


if __name__ == "__main__":
    unittest.main()
