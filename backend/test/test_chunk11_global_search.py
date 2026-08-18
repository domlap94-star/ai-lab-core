from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.database.engine import engine
from app.database.session import get_db
from app.main import app
from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_address import ClientAddress
from app.models.client_candidate import ClientCandidate
from app.models.client_contact_point import ClientContactPoint
from app.models.document import Document
from app.models.import_source import ImportSource
from app.models.inspection import Inspection
from app.models.project import Project
from app.models.user import User
from app.services.global_search_service import GlobalSearchService
from app.services.semantic_search_service import SemanticSearchResult


class _SemanticStub:
    def __init__(self, result: SemanticSearchResult | None = None, fail=False):
        self.result = result
        self.fail = fail

    def search(self, **kwargs):
        self.kwargs = kwargs
        if self.fail:
            raise ConnectionError("Qdrant unavailable")
        return [self.result] if self.result is not None else []


class GlobalSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        self.actor = self.db.query(User).filter(User.is_active.is_(True)).first()
        self.assertIsNotNone(self.actor)
        suffix = uuid.uuid4().hex[:10].translate(
            str.maketrans("0123456789", "abcdefghij")
        )
        self.term = f"Orion{suffix}"
        self.client = Client(
            client_type="company",
            name=self.term,
            legal_name=f"{self.term} Legal",
            tax_id="521-123-45-67",
            primary_email=f"{self.term}@example.com",
            primary_phone="+48 500 600 700",
            street=f"Ulica {self.term}",
            postal_code="00-123",
            city="Warszawa",
            country_code="PL",
            notes=f"Bezpieczna notatka {self.term}",
        )
        self.db.add(self.client)
        self.db.flush()
        self.db.add_all(
            [
                ClientContactPoint(
                    client_id=self.client.id,
                    kind="email",
                    value=f"secondary-{self.term}@example.com",
                    normalized_value=f"secondary-{self.term.casefold()}@example.com",
                    is_primary=False,
                    origin="manual",
                ),
                ClientContactPoint(
                    client_id=self.client.id,
                    kind="phone",
                    value="+48 501 602 703",
                    normalized_value="48501602703",
                    is_primary=False,
                    origin="manual",
                ),
                ClientAddress(
                    client_id=self.client.id,
                    label="Oddział",
                    street=f"Aleja {self.term}",
                    postal_code="01-234",
                    city=f"Miasto {self.term}",
                    country_code="PL",
                    origin="manual",
                ),
            ]
        )
        self.project = Project(
            client_id=self.client.id,
            name=f"Projekt {self.term}",
            description=f"Opis realizacji {self.term}",
            status="active",
            street=f"Plac {self.term}",
            city="Kraków",
            created_by_user_id=self.actor.id,
        )
        self.db.add(self.project)
        self.db.flush()
        self.inspection = Inspection(
            project_id=self.project.id,
            client_id=self.client.id,
            title=f"Wizja {self.term}",
            notes=f"Kontrola {self.term}",
            status="planned",
            scheduled_at=datetime.now(UTC),
            created_by_user_id=self.actor.id,
        )
        self.db.add(self.inspection)
        self.db.flush()
        self.document = Document(
            filename=f"raport-{self.term}.pdf",
            original_filename=f"Raport {self.term}.pdf",
            content_type="application/pdf",
            file_size=100,
            source_type="manual_upload",
            client_id=self.client.id,
            project_id=self.project.id,
            inspection_id=self.inspection.id,
            extracted_text=f"Treść dokumentu {self.term} bez sekretów",
            processing_status="processed",
            metadata_status="processed",
            metadata_normalized={"title": f"Metadata {self.term}"},
            match_status="matched",
        )
        self.db.add(self.document)
        self.source = ImportSource(
            source_type="gmail",
            display_name=f"Search Gmail {suffix}",
            status="active",
        )
        self.candidate = ClientCandidate(
            client_type="person",
            name=f"Kandydat {self.term}",
            primary_email=f"candidate-{self.term}@example.com",
            status="accepted",
            confidence=1,
            matched_client_id=self.client.id,
        )
        self.pending_candidate = ClientCandidate(
            client_type="person",
            name=f"Pending {self.term}",
            primary_phone="600700800",
            status="pending",
            confidence=0.8,
        )
        self.db.add_all([self.source, self.candidate, self.pending_candidate])
        self.db.flush()
        self.email = CandidateSource(
            candidate_id=self.candidate.id,
            import_source_id=self.source.id,
            source_type="gmail_message",
            external_id=f"message-{suffix}",
            source_label="Inbox",
            extracted_text=f"Aktualna wiadomość {self.term}",
            raw_payload={
                "subject": f"Temat {self.term}",
                "from": f"Nadawca <sender-{self.term}@example.com>",
                "to": "crm@example.com",
                "text": f"Aktualna wiadomość {self.term}\n\nOn Monday quoted@example.com wrote:\nSECRET QUOTED BODY",
                "date": datetime.now(UTC).isoformat(),
                "direction": "received",
            },
        )
        self.db.add(self.email)
        self.db.flush()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def search(self, query: str, *, types=None, semantic=False):
        return GlobalSearchService(
            self.db, semantic_service=_SemanticStub()
        ).search(
            query=query,
            types=types or (
                "client", "project", "inspection", "document", "email", "candidate"
            ),
            limit=50,
            semantic=semantic,
        )

    def test_all_entity_types_routes_and_bounded_payload(self) -> None:
        page = self.search(self.term)
        kinds = {item.type for item in page.items}
        self.assertEqual(
            kinds,
            {"client", "project", "inspection", "document", "email", "candidate"},
        )
        routes = {item.type: item.route for item in page.items}
        self.assertEqual(routes["client"], f"/clients/{self.client.id}")
        self.assertEqual(routes["project"], f"/projects/{self.project.id}")
        self.assertEqual(routes["inspection"], f"/inspections/{self.inspection.id}")
        self.assertEqual(routes["document"], f"/documents?document_id={self.document.id}")
        self.assertEqual(
            routes["email"],
            f"/clients/{self.client.id}?email_source_id={self.email.id}",
        )
        serialized = json.dumps(page.model_dump(mode="json"), ensure_ascii=False)
        self.assertNotIn("raw_payload", serialized)
        self.assertNotIn("SECRET QUOTED BODY", serialized)
        self.assertTrue(all(len(item.snippet or "") <= 260 for item in page.items))

    def test_client_structured_fields_and_normalization(self) -> None:
        cases = {
            self.client.name: "name",
            self.client.primary_email.upper(): "email",
            f"secondary-{self.term}@EXAMPLE.COM": "email",
            "500600700": "phone",
            "+48 501 602 703": "phone",
            "5211234567": "nip",
            f"Aleja {self.term}": "address",
            "01-234": "address",
        }
        for query, reason in cases.items():
            with self.subTest(query=query):
                page = self.search(query, types=("client",))
                hit = next(item for item in page.items if item.id == self.client.id)
                self.assertIn(reason, hit.match_reasons)

    def test_exact_result_outranks_semantic_and_document_is_collapsed(self) -> None:
        semantic = _SemanticStub(
            SemanticSearchResult(
                score=0.99,
                chunk_id=1,
                document_id=self.document.id,
                chunk_index=0,
                page_from=1,
                page_to=1,
                client_id=self.client.id,
                filename=self.document.original_filename,
                content_type=self.document.content_type,
                content_source="text",
                content=f"Semantyczna treść {self.term}",
            )
        )
        page = GlobalSearchService(
            self.db, semantic_service=semantic
        ).search(query=self.term, limit=50, semantic=True)
        self.assertEqual(page.items[0].type, "client")
        documents = [item for item in page.items if item.type == "document"]
        self.assertEqual(len(documents), 1)
        self.assertIn("semantic", documents[0].match_reasons)
        self.assertTrue(semantic.kwargs["create_collection_if_missing"] is False)

    def test_type_filter_pagination_and_semantic_fail_open(self) -> None:
        entity = lambda item: (item.type, item.id, item.score, item.route)
        failed = GlobalSearchService(
            self.db, semantic_service=_SemanticStub(fail=True)
        ).search(query=self.term, types=("client", "document"), limit=1)
        self.assertEqual(failed.semantic_status, "unavailable")
        self.assertTrue(failed.items)
        self.assertTrue(failed.has_more)
        second = GlobalSearchService(
            self.db, semantic_service=_SemanticStub(fail=True)
        ).search(query=self.term, types=("client", "document"), skip=1, limit=1)
        combined = GlobalSearchService(
            self.db, semantic_service=_SemanticStub(fail=True)
        ).search(query=self.term, types=("client", "document"), limit=2)
        self.assertNotEqual(entity(failed.items[0]), entity(second.items[0]))
        self.assertEqual(
            [entity(failed.items[0]), entity(second.items[0])],
            [entity(item) for item in combined.items],
        )
        self.assertFalse(second.has_more)
        self.assertEqual(second.semantic_status, "unavailable")
        only_projects = self.search(self.term, types=("project",))
        self.assertTrue(only_projects.items)
        self.assertTrue(all(item.type == "project" for item in only_projects.items))

    def test_pagination_is_disjoint_stable_and_matches_reference(self) -> None:
        entity = lambda item: (item.type, item.id, item.score, item.route)
        service = GlobalSearchService(self.db, semantic_service=_SemanticStub())
        reference = service.search(query=self.term, semantic=False, limit=50)
        first = service.search(query=self.term, semantic=False, limit=5)
        second = service.search(query=self.term, semantic=False, skip=5, limit=5)

        first_keys = [entity(item) for item in first.items]
        second_keys = [entity(item) for item in second.items]
        self.assertFalse(
            {(item.type, item.id) for item in first.items}
            & {(item.type, item.id) for item in second.items}
        )
        self.assertEqual(
            first_keys + second_keys,
            [entity(item) for item in reference.items[:10]],
        )
        self.assertEqual(first.has_more, len(reference.items) > 5)
        self.assertEqual(second.has_more, len(reference.items) > 10)

        repeated = [
            [
                entity(item)
                for item in service.search(
                    query=self.term, semantic=False, limit=50
                ).items
            ]
            for _ in range(3)
        ]
        self.assertEqual(repeated, [repeated[0], repeated[0], repeated[0]])

    def test_type_filtered_pagination_allows_same_type_on_both_pages(self) -> None:
        second_client = Client(
            client_type="company",
            name=f"Oddział {self.term}",
        )
        self.db.add(second_client)
        self.db.flush()
        service = GlobalSearchService(self.db, semantic_service=_SemanticStub())
        first = service.search(
            query=self.term,
            types=("client",),
            semantic=False,
            limit=1,
        )
        second = service.search(
            query=self.term,
            types=("client",),
            semantic=False,
            skip=1,
            limit=1,
        )
        self.assertEqual(first.items[0].type, "client")
        self.assertEqual(second.items[0].type, "client")
        self.assertNotEqual(first.items[0].id, second.items[0].id)
        self.assertTrue(first.has_more)
        self.assertFalse(second.has_more)

        mixed = self.search(self.term, types=("document", "email"))
        self.assertTrue(mixed.items)
        self.assertTrue(
            all(item.type in {"document", "email"} for item in mixed.items)
        )

    def test_bounded_query_count_has_no_per_result_n_plus_one(self) -> None:
        statements: list[str] = []

        def capture(*args) -> None:
            statements.append(str(args[2]))

        event.listen(self.connection, "before_cursor_execute", capture)
        try:
            self.search(self.term)
        finally:
            event.remove(self.connection, "before_cursor_execute", capture)
        self.assertLessEqual(len(statements), 12)

    def test_endpoint_auth_validation_filter_and_limit(self) -> None:
        def override_db():
            yield self.db

        client = TestClient(app)
        self.assertIn(client.get("/api/v1/search?q=orion").status_code, (401, 403))
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: self.actor
        response = client.get(
            f"/api/v1/search?q={self.term}&types=client&semantic=false"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(all(item["type"] == "client" for item in response.json()["items"]))
        self.assertEqual(client.get("/api/v1/search?q=x").status_code, 422)
        self.assertEqual(
            client.get("/api/v1/search?q=orion&types=secret").status_code,
            422,
        )
        self.assertEqual(
            client.get("/api/v1/search?q=orion&limit=999").status_code,
            422,
        )

    def test_search_index_migration_is_additive_only(self) -> None:
        migration = Path(
            "/app/alembic/versions/"
            "chunk11search_20260818_add_global_search_indexes.py"
        ).read_text(encoding="utf-8")
        upgrade = migration.split("def downgrade", 1)[0].upper()
        self.assertIn('DOWN_REVISION = "PRECHUNK11STATUS_20260817"', upgrade)
        self.assertIn("CREATE INDEX IX_CANDIDATE_SOURCES_GMAIL_SEARCH_VECTOR", upgrade)
        self.assertIn("SOURCE_TYPE = 'GMAIL_MESSAGE'", upgrade)
        self.assertIn("DELETED_AT IS NULL", upgrade)
        self.assertNotIn("DROP ", upgrade)
        self.assertNotIn("UPDATE ", upgrade)
        self.assertNotIn("INSERT ", upgrade)


if __name__ == "__main__":
    unittest.main()
