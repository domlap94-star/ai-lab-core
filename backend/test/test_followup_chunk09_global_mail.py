from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import app
from app.repositories.global_mail_repository import GlobalMailRepository
from app.repositories.global_mail_repository import IGNORED_SQL
from app.schemas.global_mail import GlobalMailListItem
from app.services.client_email_service import ClientEmailService


class _Result:
    def mappings(self):
        return self

    def __iter__(self):
        return iter(())


class _Session:
    def __init__(self) -> None:
        self.sql = ""
        self.params = {}

    def execute(self, statement, params):
        self.sql = str(statement)
        self.params = params
        return _Result()


BASE = dict(
    search=None,
    client_id=None,
    direction=None,
    linked=None,
    has_attachments=None,
    read_state=None,
    date_from=None,
    date_to=None,
    thread_id=None,
    skip=0,
    limit=50,
)


class GlobalMailQueryContractTests(unittest.TestCase):
    def _query(self, **changes):
        session = _Session()
        GlobalMailRepository(session).get_page(**(BASE | changes))
        return session.sql, session.params

    def test_latest_is_bounded_and_ordered(self):
        sql, params = self._query()
        self.assertIn("LIMIT :fetch", sql)
        self.assertIn("cs.id DESC", sql)
        self.assertEqual(params["fetch"], 51)

    def test_received_filter(self):
        sql, params = self._query(direction="received")
        self.assertIn("=:direction", sql)
        self.assertEqual(params["direction"], "received")

    def test_sent_filter(self):
        _, params = self._query(direction="sent")
        self.assertEqual(params["direction"], "sent")

    def test_unknown_direction_filter(self):
        _, params = self._query(direction="unknown")
        self.assertEqual(params["direction"], "unknown")

    def test_read_filter_uses_full_index_order(self):
        sql, params = self._query(read_state="read")
        self.assertIn("=:read_state", sql)
        self.assertLess(sql.rfind("labelIds"), sql.rfind("created_at"))
        self.assertEqual(params["read_state"], "read")

    def test_unread_filter(self):
        _, params = self._query(read_state="unread")
        self.assertEqual(params["read_state"], "unread")

    def test_unknown_read_is_null(self):
        sql, _ = self._query(read_state="unknown")
        self.assertIn("IS NULL", sql)
        self.assertNotIn("read_state", _)

    def test_search_uses_existing_fts(self):
        sql, params = self._query(search="invoice")
        self.assertIn("plainto_tsquery", sql)
        self.assertEqual(params["search"], "invoice")

    def test_linked_filter(self):
        sql, _ = self._query(linked=True)
        self.assertIn("matched_client_id IS NOT NULL", sql)

    def test_unlinked_filter(self):
        sql, _ = self._query(linked=False)
        self.assertIn("NOT (cc.matched_client_id IS NOT NULL", sql)

    def test_client_filter(self):
        sql, params = self._query(client_id=42)
        self.assertIn("cc.matched_client_id=:client_id", sql)
        self.assertEqual(params["client_id"], 42)

    def test_attachment_filter(self):
        sql, _ = self._query(has_attachments=True)
        self.assertIn("EXISTS (SELECT 1 FROM documents", sql)

    def test_date_from(self):
        value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        _, params = self._query(date_from=value)
        self.assertEqual(params["date_from"], value)

    def test_date_to(self):
        value = datetime(2026, 8, 19, tzinfo=timezone.utc)
        _, params = self._query(date_to=value)
        self.assertEqual(params["date_to"], value)

    def test_thread_filter_uses_canonical_column(self):
        sql, params = self._query(thread_id="opaque-thread")
        self.assertIn("cs.external_parent_id=:thread_id", sql)
        self.assertEqual(params["thread_id"], "opaque-thread")

    def test_no_raw_payload_in_public_list_schema(self):
        self.assertNotIn("raw_payload", GlobalMailListItem.model_fields)

    def test_ignored_state_is_bound_to_source_sender_not_candidate_email(self):
        self.assertNotIn("cc.primary_email", IGNORED_SQL)
        self.assertIn("cs.raw_payload", IGNORED_SQL)

    def test_unknown_read_state_is_publicly_supported(self):
        item = GlobalMailListItem(
            source_id=2,
            message_id="technical-id",
            direction="unknown",
            read_state="unknown",
            occurred_at=datetime.now(timezone.utc),
            has_attachments=False,
            attachment_count=0,
        )
        self.assertEqual(item.read_state, "unknown")


class GlobalMailBodySafetyTests(unittest.TestCase):
    def setUp(self):
        self.service = ClientEmailService(Mock())

    def test_html_scripts_and_styles_are_removed(self):
        result = self.service._body_text(
            {"html": "<style>secret</style><p>Hello</p><script>bad()</script>"},
            None,
        )
        self.assertEqual(result, "Hello")

    def test_detail_body_is_bounded(self):
        result = self.service._body_text({"text": "x" * 120_000}, None)
        self.assertEqual(len(result), 100_000)

    def test_plain_text_is_preserved(self):
        self.assertEqual(self.service._body_text({"text": "Hello"}, None), "Hello")

    def test_no_remote_content_is_fetched(self):
        result = self.service._body_text(
            {"html": '<img src="https://tracker.invalid/pixel"><p>Safe</p>'},
            None,
        )
        self.assertEqual(result, "Safe")


class GlobalMailAuthTests(unittest.TestCase):
    def test_list_requires_jwt(self):
        response = TestClient(app).get("/api/v1/mail")
        self.assertEqual(response.status_code, 401)

    def test_detail_requires_jwt(self):
        response = TestClient(app).get("/api/v1/mail/2")
        self.assertEqual(response.status_code, 401)

    def test_thread_requires_jwt(self):
        response = TestClient(app).get("/api/v1/mail/threads/example")
        self.assertEqual(response.status_code, 401)

    def test_compose_requires_jwt(self):
        response = TestClient(app).post("/api/v1/mail/send", json={})
        self.assertEqual(response.status_code, 401)

    def test_reply_requires_jwt(self):
        response = TestClient(app).post("/api/v1/mail/2/reply", json={})
        self.assertEqual(response.status_code, 401)

    def test_forward_requires_jwt(self):
        response = TestClient(app).post("/api/v1/mail/2/forward", json={})
        self.assertEqual(response.status_code, 401)


class GlobalMailSendRouteUniquenessTests(unittest.TestCase):
    def test_send_routes_are_registered_exactly_once(self):
        expected = (
            "/api/v1/mail/send",
            "/api/v1/mail/{source_id}/reply",
            "/api/v1/mail/{source_id}/forward",
        )
        post_routes = [
            route.path
            for route in app.routes
            if "POST" in getattr(route, "methods", set())
        ]
        for path in expected:
            self.assertEqual(post_routes.count(path), 1, path)

    def test_router_source_has_one_send_structure(self):
        source = (Path(__file__).parents[1] / "app" / "api" / "mail.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("from app.schemas.mail_send import"), 1)
        self.assertEqual(source.count("from app.services.mail_send_service import"), 1)
        self.assertEqual(source.count("def _send_error("), 1)
        self.assertEqual(source.count('@router.post("/send"'), 1)
        self.assertEqual(source.count('@router.post("/{source_id}/reply"'), 1)
        self.assertEqual(source.count('@router.post("/{source_id}/forward"'), 1)


if __name__ == "__main__":
    unittest.main()
