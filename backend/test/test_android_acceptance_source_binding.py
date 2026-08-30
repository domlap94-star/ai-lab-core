from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest
from unittest.mock import Mock
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()

from app.database.global_mail_sql import GMAIL_SENDER_EMAIL_SQL
from app.database.session import SessionLocal
from app.models.assistant_pipeline import (
    AssistantRun,
    AssistantRunMaterial,
    AssistantRunStage,
)
from app.models.document import Document
from app.models.role import Role
from app.models.user import User
from app.repositories.client_email_repository import ClientEmailRepository
from app.repositories.global_mail_repository import IGNORED_SQL
from app.schemas.agent import AgentSource
from app.services.assistant_run_material_service import (
    AssistantMaterialSourceRefConflict,
    AssistantRunMaterialService,
)
from app.services.assistant_run_stage_service import AssistantRunStageService
from app.services.candidate_context_service import CandidateContextService
from app.services.client_email_service import ClientEmailService
from app.services.global_mail_service import GlobalMailService
from app.services.mail_sender_authority import canonical_mail_addresses


class AssistantMaterialBindingIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SessionLocal()
        assert_isolated_database(self.db, TEST_DATABASE_NAME)
        self.assertFalse(self.db.autoflush)
        suffix = uuid4().hex
        role = Role(
            name=f"material-{suffix[:12]}",
            description="Isolated Assistant material test",
        )
        self.db.add(role)
        self.db.flush()
        user = User(
            username=f"material-{suffix[:20]}",
            email=f"material-{suffix[:20]}@test.invalid",
            password_hash="not-used",
            role_id=role.id,
        )
        self.db.add(user)
        self.db.flush()
        self.run = AssistantRun(
            id=str(uuid4()),
            created_by_user_id=user.id,
            attempt_id=f"material-{suffix[:16]}",
            orchestrator_version="test",
            evidence_contract_version="test",
            policy_generation="test",
            input_fingerprint="a" * 64,
            request_payload={"question": "synthetic"},
            target_scope={},
            complexity="standard",
            sensitivity="public_reference",
        )
        self.db.add(self.run)
        self.db.flush()

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.close()

    @staticmethod
    def source(
        source_id: int,
        *,
        title: str = "Synthetic KB source",
        snippet: str = "Bounded public-safe evidence.",
        route: str | None = None,
        source_type: str = "knowledge_base",
    ) -> AgentSource:
        return AgentSource(
            source_type=source_type,
            source_id=source_id,
            title=title,
            snippet=snippet,
            route=route or f"/knowledge-base/{source_id}",
        )

    def materials(self) -> list[AssistantRunMaterial]:
        return (
            self.db.query(AssistantRunMaterial)
            .filter(AssistantRunMaterial.assistant_run_id == self.run.id)
            .order_by(AssistantRunMaterial.id)
            .all()
        )

    def test_same_kb_entity_twice_is_one_material_with_aliases(self) -> None:
        AssistantRunMaterialService(self.db).bind_collected_sources(
            run_id=self.run.id,
            sources=[self.source(7), self.source(7, route="/search/kb/7")],
        )
        rows = self.materials()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].source_ref, "S01")
        self.assertEqual(rows[0].source_manifest["source_refs"], ["S01", "S02"])

    def test_dispatcher_evidence_stage_completes_with_duplicate_kb_entity(self) -> None:
        stage = AssistantRunStage(
            id=str(uuid4()),
            assistant_run_id=self.run.id,
            stage_key="04-retrieving-case-evidence",
            stage_type="retrieving_case_evidence",
            ordinal=4,
            inactivity_timeout_seconds=60,
            absolute_cap_seconds=120,
        )
        self.db.add(stage)
        self.db.flush()
        stages = AssistantRunStageService(self.db)
        stages.start(self.run, "retrieving_case_evidence")
        AssistantRunMaterialService(self.db).bind_collected_sources(
            run_id=self.run.id,
            sources=[self.source(7), self.source(7, route="/search/kb/7")],
        )
        stages.complete(
            self.run,
            "retrieving_case_evidence",
            result_manifest={"source_count": 0},
        )
        self.db.flush()
        self.assertEqual(stage.status, "completed")
        self.assertEqual(len(self.materials()), 1)

    def test_same_entity_three_times_preserves_all_aliases(self) -> None:
        AssistantRunMaterialService(self.db).bind_collected_sources(
            run_id=self.run.id,
            sources=[self.source(7), self.source(7), self.source(7)],
        )
        row = self.materials()[0]
        self.assertEqual(row.source_manifest["source_refs"], ["S01", "S02", "S03"])

    def test_duplicate_and_unique_keep_original_raw_positions(self) -> None:
        AssistantRunMaterialService(self.db).bind_collected_sources(
            run_id=self.run.id,
            sources=[self.source(7), self.source(7), self.source(8)],
        )
        self.assertEqual(
            [(row.source_entity_id, row.source_ref) for row in self.materials()],
            [("7", "S01"), ("8", "S03")],
        )

    def test_repeated_bind_is_idempotent_and_primary_ref_is_stable(self) -> None:
        service = AssistantRunMaterialService(self.db)
        service.bind_collected_sources(
            run_id=self.run.id,
            sources=[self.source(7), self.source(7)],
        )
        first_id = self.materials()[0].id
        service.bind_collected_sources(
            run_id=self.run.id,
            sources=[self.source(7), self.source(7), self.source(7)],
        )
        row = self.materials()[0]
        self.assertEqual(row.id, first_id)
        self.assertEqual(row.source_ref, "S01")
        self.assertEqual(row.source_manifest["source_refs"], ["S01", "S02", "S03"])
        self.assertEqual(len(row.source_manifest["observations"]), 3)

    def test_same_ref_for_different_entity_fails_closed(self) -> None:
        service = AssistantRunMaterialService(self.db)
        service.bind_collected_sources(run_id=self.run.id, sources=[self.source(7)])
        with self.assertRaisesRegex(
            AssistantMaterialSourceRefConflict,
            "ASSISTANT_MATERIAL_SOURCE_REF_CONFLICT:S01",
        ):
            service.bind_collected_sources(
                run_id=self.run.id,
                sources=[self.source(8)],
            )

    def test_same_entity_merges_distinct_bounded_provenance(self) -> None:
        AssistantRunMaterialService(self.db).bind_collected_sources(
            run_id=self.run.id,
            sources=[
                self.source(7, route="/kb/7", snippet="First excerpt"),
                self.source(7, route="/search/7", snippet="Second excerpt"),
            ],
        )
        row = self.materials()[0]
        self.assertEqual(len(row.source_manifest["observations"]), 2)
        self.assertEqual(
            [item["route"] for item in row.source_manifest["observations"]],
            ["/kb/7", "/search/7"],
        )

    def test_unique_constraints_remain_satisfied(self) -> None:
        AssistantRunMaterialService(self.db).bind_collected_sources(
            run_id=self.run.id,
            sources=[self.source(7), self.source(7), self.source(8)],
        )
        rows = self.materials()
        self.assertEqual(len({row.source_ref for row in rows}), len(rows))
        self.assertEqual(
            len(
                {
                    (row.source_domain, row.source_entity_type, row.source_entity_id)
                    for row in rows
                }
            ),
            len(rows),
        )

    def test_document_attach_remains_idempotent(self) -> None:
        document = Document(
            filename="synthetic.pdf",
            content_type="application/pdf",
            file_size=10,
            checksum_sha256="b" * 64,
            processing_status="processed",
        )
        self.db.add(document)
        self.db.flush()
        service = AssistantRunMaterialService(self.db)
        first = service.attach_document(
            run_id=self.run.id,
            document=document,
            required=True,
            preparation_job_id=None,
            artifact=None,
        )
        second = service.attach_document(
            run_id=self.run.id,
            document=document,
            required=False,
            preparation_job_id=None,
            artifact=None,
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(self.materials()), 1)
        self.assertTrue(second.required)

    def test_non_kb_material_keeps_case_fact_semantics(self) -> None:
        AssistantRunMaterialService(self.db).bind_collected_sources(
            run_id=self.run.id,
            sources=[
                self.source(19, source_type="candidate"),
                self.source(19, source_type="candidate"),
            ],
        )
        row = self.materials()[0]
        self.assertEqual(row.source_domain, "candidate")
        self.assertEqual(row.source_role, "case_fact")
        self.assertEqual(row.sensitivity, "customer_sanitizable")


class MailSenderAuthorityTests(unittest.TestCase):
    def test_structured_plain_and_display_name_shapes_are_equivalent(self) -> None:
        expected = [(None, "import-test@example.com")]
        self.assertEqual(
            canonical_mail_addresses({"address": "Import-Test@Example.COM"}),
            expected,
        )
        self.assertEqual(
            canonical_mail_addresses("Import-Test@Example.COM"),
            expected,
        )
        self.assertEqual(
            canonical_mail_addresses("Fixture Sender <Import-Test@Example.COM>"),
            [("Fixture Sender", "import-test@example.com")],
        )
        self.assertEqual(
            canonical_mail_addresses(
                {"value": [{"name": "Fixture Sender", "address": "Import-Test@Example.COM"}]}
            ),
            [("Fixture Sender", "import-test@example.com")],
        )

    def test_malformed_sender_has_no_authority(self) -> None:
        for value in (None, "", "missing-at.example.com", {"address": "x@localhost"}):
            self.assertEqual(canonical_mail_addresses(value), [])

    def test_candidate_projection_normalizes_legacy_sender(self) -> None:
        self.assertEqual(
            CandidateContextService._extract_mail_address(
                "Fixture Sender <Import-Test@Example.COM>"
            ),
            {"name": "Fixture Sender", "address": "import-test@example.com"},
        )
        self.assertEqual(
            CandidateContextService._extract_mail_address(
                {"address": "Import-Test@Example.COM"}
            ),
            {"name": None, "address": "import-test@example.com"},
        )

    def test_client_email_sender_path_uses_same_authority(self) -> None:
        self.assertEqual(
            ClientEmailService._addresses({"address": "Import-Test@Example.COM"}),
            [(None, "import-test@example.com")],
        )
        self.assertEqual(
            ClientEmailService._addresses("Import-Test@Example.COM"),
            [(None, "import-test@example.com")],
        )

    def test_global_mail_projection_exposes_legacy_sender(self) -> None:
        service = object.__new__(GlobalMailService)
        service.client_email = ClientEmailService(Mock())
        row = {
            "source_id": 2,
            "message_id": "fixture-message",
            "thread_id": "fixture-thread",
            "raw_payload": {"from": "Import-Test@Example.COM"},
            "occurred_at": datetime.now(timezone.utc),
            "direction": "unknown",
            "read_state": "unknown",
            "client_id": None,
            "client_name": None,
            "review_state": "rejected",
            "ignored": False,
            "attachment_count": 0,
        }
        item = service._list_item(row)
        self.assertEqual(item.sender, "import-test@example.com")
        self.assertEqual(item.direction, "unknown")

    def test_postgresql_sender_projection_matches_supported_shapes(self) -> None:
        db = SessionLocal()
        try:
            assert_isolated_database(db, TEST_DATABASE_NAME)
            statement = text(
                "SELECT (" + GMAIL_SENDER_EMAIL_SQL + ") "
                "FROM (SELECT CAST(:payload AS json) AS raw_payload) fixture"
            )
            shapes = (
                {"from": {"address": "Import-Test@Example.COM"}},
                {"from": "Import-Test@Example.COM"},
                {"from": "Fixture Sender <Import-Test@Example.COM>"},
                {
                    "from": {
                        "value": [
                            {
                                "name": "Fixture Sender",
                                "address": "Import-Test@Example.COM",
                            }
                        ]
                    }
                },
            )
            for payload in shapes:
                self.assertEqual(
                    db.execute(
                        statement, {"payload": json.dumps(payload)}
                    ).scalar_one(),
                    "import-test@example.com",
                )
            self.assertIsNone(
                db.execute(
                    statement,
                    {"payload": json.dumps({"from": "missing-at.example.com"})},
                ).scalar_one()
            )
        finally:
            db.rollback()
            db.close()

    def test_ignored_matching_uses_source_sender_not_candidate_identity(self) -> None:
        self.assertNotIn("cc.primary_email", IGNORED_SQL)
        db = SessionLocal()
        try:
            assert_isolated_database(db, TEST_DATABASE_NAME)
            query = ClientEmailRepository(db)._deduplicated_sources(7)
            sql = str(
                query.select().compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            )
            self.assertNotIn("lower(client_candidates.primary_email)", sql)
            self.assertIn("candidate_sources.raw_payload", sql)
        finally:
            db.rollback()
            db.close()


if __name__ == "__main__":
    unittest.main()
