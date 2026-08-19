from __future__ import annotations

import os
import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.candidate_source import CandidateSource
from app.models.mail_send_operation import MailSendOperation
from app.models.user import User
from app.schemas.mail_send import MailSendRequest
from app.services.mail_provider_adapter import (
    MailProviderDefinitiveError,
    MailProviderResult,
    MailProviderUnknownError,
)
from app.services.mail_send_service import MailSendConflictError, MailSendService


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

    def send(self, payload):
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
        if os.environ.get("POSTGRES_DB") == "ai_lab":
            raise RuntimeError("Refusing to run send tests on production")
        cls.engine = create_engine(database_url())
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


if __name__ == "__main__":
    unittest.main()
