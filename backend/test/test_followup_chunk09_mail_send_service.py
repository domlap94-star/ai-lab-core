from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)

from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.document import Document
from app.models.mail_send_operation import MailSendOperation
from app.models.user import User
from app.schemas.mail_send import MailSendRequest
from app.services.mail_provider_adapter import (
    MailProviderDefinitiveError,
    MailProviderResult,
    MailProviderUnknownError,
    N8nMailProviderAdapter,
)
from app.services.mail_send_service import MailSendConflictError, MailSendService, MailSendValidationError


def database_url() -> str:
    return (
        f"postgresql+psycopg://{os.environ['POSTGRES_USER']}:"
        f"{os.environ['POSTGRES_PASSWORD']}@{os.environ.get('POSTGRES_HOST', 'postgres')}:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/{os.environ['POSTGRES_DB']}"
    )


class Provider:
    def __init__(self, mode="success"):
        self.mode = mode
        self.calls = 0
        self._lock = Lock()

    def send(self, payload):
        with self._lock:
            self.calls += 1
        if self.mode == "definitive":
            raise MailProviderDefinitiveError("synthetic_rejected")
        if self.mode == "unknown":
            raise MailProviderUnknownError
        return MailProviderResult(
            message_id=f"synthetic-{payload['operation_id']}",
            thread_id=f"thread-{payload['operation_id']}",
            execution_ref="synthetic-execution",
        )


class MailSendServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_name = require_test_database_environment()
        cls.engine = create_engine(database_url())
        assert_isolated_database(cls.engine, database_name)
        cls.Session = sessionmaker(bind=cls.engine)

    def setUp(self):
        self.db = self.Session()
        self.actor = self.db.query(User).order_by(User.id).first()
        self.assertIsNotNone(self.actor)

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def request(self, operation_id=None, body="synthetic body"):
        return MailSendRequest(
            operation_id=operation_id or uuid4(),
            to=["acceptance@example.invalid"],
            subject="NEXT Stabil CHUNK 09 acceptance test",
            body=body,
        )

    def test_success_replay_and_payload_conflict(self):
        provider = Provider()
        service = MailSendService(self.db, provider)
        request = self.request()
        first = service.compose(self.actor, request)
        self.assertEqual(first.status, "canonical_synced")
        replay = service.compose(self.actor, request)
        self.assertTrue(replay.replayed)
        self.assertEqual(provider.calls, 1)
        with self.assertRaises(MailSendConflictError):
            service.compose(self.actor, request.model_copy(update={"body": "changed"}))
        self.assertEqual(provider.calls, 1)

    def test_definitive_and_unknown_are_fail_closed(self):
        definitive = Provider("definitive")
        failed = MailSendService(self.db, definitive).compose(self.actor, self.request())
        self.assertEqual(failed.status, "failed")

        unknown_provider = Provider("unknown")
        request = self.request()
        unknown = MailSendService(self.db, unknown_provider).compose(self.actor, request)
        self.assertEqual(unknown.status, "unknown")
        second = MailSendService(self.db, unknown_provider).compose(self.actor, request)
        self.assertEqual(second.status, "unknown")
        self.assertEqual(unknown_provider.calls, 1)

    def test_ledger_contains_no_message_content(self):
        provider = Provider("definitive")
        request = self.request(body="SECRET SYNTHETIC BODY")
        MailSendService(self.db, provider).compose(self.actor, request)
        row = self.db.query(MailSendOperation).filter(MailSendOperation.operation_id == request.operation_id).one()
        values = " ".join(str(value) for value in row.__dict__.values())
        self.assertNotIn(request.body, values)
        self.assertNotIn(request.subject, values)
        self.assertNotIn(request.to[0], values)

    def test_provider_accepted_ingest_failure_never_resends(self):
        provider = Provider()
        request = self.request()
        service = MailSendService(self.db, provider)
        with patch.object(service, "_canonical_ingest", side_effect=RuntimeError("synthetic ingest failure")):
            first = service.compose(self.actor, request)
            replay = service.compose(self.actor, request)
        self.assertEqual(first.status, "provider_accepted")
        self.assertEqual(replay.status, "provider_accepted")
        self.assertEqual(provider.calls, 1)

    def test_concurrent_operation_claim_calls_provider_once(self):
        provider = Provider()
        request = self.request()

        def send_once():
            db = self.Session()
            try:
                actor = db.query(User).filter(User.id == self.actor.id).one()
                return MailSendService(db, provider).compose(actor, request).status
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(lambda _: send_once(), range(2)))

        self.assertEqual(provider.calls, 1)
        self.assertIn("canonical_synced", statuses)
        self.assertEqual(
            self.db.query(MailSendOperation).filter(MailSendOperation.operation_id == request.operation_id).count(),
            1,
        )

    def test_cross_client_attachment_is_rejected_before_file_read(self):
        owner = Client(client_type="company", name=f"Attachment owner {uuid4()}", country_code="PL")
        other = Client(client_type="company", name=f"Attachment other {uuid4()}", country_code="PL")
        self.db.add_all([owner, other])
        self.db.flush()
        document = Document(
            filename="synthetic.txt",
            original_filename="synthetic.txt",
            content_type="text/plain",
            file_size=9,
            storage_path="must-not-be-read.txt",
            client_id=owner.id,
        )
        self.db.add(document)
        self.db.commit()

        request = self.request().model_copy(
            update={"client_id": other.id, "attachment_document_ids": [document.id]}
        )
        provider = Provider()
        with self.assertRaisesRegex(MailSendValidationError, "attachment_forbidden"):
            MailSendService(self.db, provider).compose(self.actor, request)
        self.assertEqual(provider.calls, 0)

    @patch("app.services.mail_provider_adapter.httpx.post")
    def test_non_json_provider_response_is_unknown(self, post):
        response = post.return_value
        response.status_code = 200
        response.json.side_effect = ValueError("not json")
        with self.assertRaises(MailProviderUnknownError):
            N8nMailProviderAdapter().send({"action": "compose"})


if __name__ == "__main__":
    unittest.main()
