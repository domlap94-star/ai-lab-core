from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()

from app.api.auth import get_current_user
from app.database.engine import engine
from app.database.session import get_db
from app.api.documents.router import router as documents_router
from app.api.search.router import router as search_router
from app.models.client import Client
from app.models.client_access_grant import ClientAccessGrant
from app.models.document import Document
from app.models.inspection import Inspection
from app.models.project import Project
from app.models.role import Role
from app.models.user import User
from app.services.client_search_matching_service import ClientSearchQuery
from app.services.global_search_service import GlobalSearchService
from app.services.semantic_search_service import SemanticSearchResult


class _SemanticFixture:
    def __init__(self, document_ids: list[int]) -> None:
        self.document_ids = document_ids

    def search(self, **kwargs):
        del kwargs
        return [
            SemanticSearchResult(
                score=0.9,
                chunk_id=index,
                document_id=document_id,
                chunk_index=0,
                page_from=1,
                page_to=1,
                client_id=None,
                filename=f"fixture-{index}.txt",
                content_type="text/plain",
                content_source="text",
                content="controlled semantic fixture",
            )
            for index, document_id in enumerate(self.document_ids, start=1)
        ]


class R25ExternalSearchScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        assert_isolated_database(engine, TEST_DATABASE_NAME)
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        suffix = uuid.uuid4().hex[:12]
        self.term = f"r25search{suffix}"

        roles = {
            role.name: role
            for role in self.db.query(Role).filter(
                Role.name.in_(("Administrator", "User", "External"))
            )
        }
        for name in ("Administrator", "User", "External"):
            if name not in roles:
                roles[name] = Role(name=name, description=name)
                self.db.add(roles[name])
        self.db.flush()
        self.probe = FastAPI()
        self.probe.include_router(documents_router, prefix="/api/v1")
        self.probe.include_router(search_router, prefix="/api/v1")

        def make_user(label: str, role: Role) -> User:
            return User(
                username=f"{self.term}_{label}",
                email=f"{self.term}_{label}@example.invalid",
                password_hash="not-used",
                is_active=True,
                role=role,
            )

        self.admin = make_user("admin", roles["Administrator"])
        self.user = make_user("user", roles["User"])
        self.external = make_user("external", roles["External"])
        self.client_a = Client(client_type="company", name=f"{self.term} A", country_code="PL")
        self.client_b = Client(client_type="company", name=f"{self.term} B", country_code="PL")
        self.db.add_all(
            [self.admin, self.user, self.external, self.client_a, self.client_b]
        )
        self.db.flush()

        self.project_a = Project(
            client_id=self.client_a.id,
            name=f"{self.term} project A",
            status="active",
            country_code="PL",
            created_by_user_id=self.admin.id,
        )
        self.project_b = Project(
            client_id=self.client_b.id,
            name=f"{self.term} project B",
            status="active",
            country_code="PL",
            created_by_user_id=self.admin.id,
        )
        self.db.add_all([self.project_a, self.project_b])
        self.db.flush()
        self.inspection_a = Inspection(
            client_id=self.client_a.id,
            project_id=self.project_a.id,
            title=f"{self.term} inspection A",
            status="planned",
            created_by_user_id=self.admin.id,
        )
        self.inspection_b = Inspection(
            client_id=self.client_b.id,
            project_id=self.project_b.id,
            title=f"{self.term} inspection B",
            status="planned",
            created_by_user_id=self.admin.id,
        )
        self.db.add_all([self.inspection_a, self.inspection_b])
        self.db.flush()
        self.db.add(
            ClientAccessGrant(
                client_id=self.client_a.id,
                external_user_id=self.external.id,
                granted_by_user_id=self.admin.id,
                granted_at=datetime.now(UTC),
            )
        )

        def document(label: str, **owners) -> Document:
            return Document(
                filename=f"{self.term}-{label}.txt",
                original_filename=f"{self.term}-{label}.txt",
                content_type="text/plain",
                file_size=1,
                source_type="manual_upload",
                extracted_text=f"{self.term} {label}",
                processing_status="processed",
                metadata_status="processed",
                match_status="matched",
                **owners,
            )

        self.direct_a = document("direct-a", client_id=self.client_a.id)
        self.project_doc_a = document("project-a", project_id=self.project_a.id)
        self.inspection_doc_a = document(
            "inspection-a", inspection_id=self.inspection_a.id
        )
        self.direct_b = document("direct-b", client_id=self.client_b.id)
        self.project_doc_b = document("project-b", project_id=self.project_b.id)
        self.inspection_doc_b = document(
            "inspection-b", inspection_id=self.inspection_b.id
        )
        self.unowned = document("unowned")
        self.mixed = document(
            "mixed-a-b", client_id=self.client_a.id, project_id=self.project_b.id
        )
        self.db.add_all(
            [
                self.direct_a,
                self.project_doc_a,
                self.inspection_doc_a,
                self.direct_b,
                self.project_doc_b,
                self.inspection_doc_b,
                self.unowned,
                self.mixed,
            ]
        )
        self.db.flush()
        now = datetime.now(UTC)
        for offset, item in enumerate(
            (
                self.direct_a,
                self.project_doc_a,
                self.inspection_doc_a,
                self.direct_b,
                self.project_doc_b,
                self.inspection_doc_b,
                self.unowned,
                self.mixed,
            )
        ):
            item.updated_at = now + timedelta(seconds=offset)
        self.db.flush()

    def tearDown(self) -> None:
        self.probe.dependency_overrides.clear()
        self.db.close()
        self.transaction.rollback()
        self.connection.close()

    def service(self, viewer: User, semantic_ids: list[int] | None = None):
        return GlobalSearchService(
            self.db,
            viewer=viewer,
            semantic_service=_SemanticFixture(semantic_ids or []),
        )

    def test_external_document_predicate_compiles_with_local_exists_froms(self) -> None:
        service = self.service(self.external)
        query = (
            self.db.query(Document)
            .outerjoin(Project, Project.id == Document.project_id)
            .outerjoin(Inspection, Inspection.id == Document.inspection_id)
            .filter(service._document_allowed())
        )
        sql = str(
            query.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).lower()
        self.assertIn("from projects as", sql)
        self.assertIn("from inspections as", sql)

    def test_external_lexical_endpoint_returns_only_unambiguous_a_documents(self) -> None:
        self.probe.dependency_overrides[get_db] = lambda: self.db
        self.probe.dependency_overrides[get_current_user] = lambda: self.external
        with TestClient(self.probe) as client:
            response = client.get(
                "/api/v1/search",
                params={
                    "q": self.term,
                    "types": "document",
                    "semantic": "false",
                    "limit": 50,
                },
            )
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.json()["items"]}
        self.assertEqual(
            ids,
            {self.direct_a.id, self.project_doc_a.id, self.inspection_doc_a.id},
        )
        serialized = response.text
        for hidden in (
            self.direct_b,
            self.project_doc_b,
            self.inspection_doc_b,
            self.unowned,
            self.mixed,
        ):
            self.assertNotIn(hidden.filename, serialized)

    def test_external_semantic_results_use_the_same_fail_closed_scope(self) -> None:
        service = self.service(
            self.external,
            [
                self.direct_a.id,
                self.project_doc_a.id,
                self.inspection_doc_a.id,
                self.direct_b.id,
                self.project_doc_b.id,
                self.inspection_doc_b.id,
                self.unowned.id,
                self.mixed.id,
            ],
        )
        q = ClientSearchQuery(
            value=self.term,
            folded=self.term.casefold(),
            digits="",
            phone_digits="",
        )
        ids = {item.id for item in service._semantic_documents(q, 50)}
        self.assertEqual(
            ids,
            {self.direct_a.id, self.project_doc_a.id, self.inspection_doc_a.id},
        )

    def test_document_direct_id_is_indistinguishable_outside_external_scope(self) -> None:
        self.probe.dependency_overrides[get_db] = lambda: self.db
        self.probe.dependency_overrides[get_current_user] = lambda: self.external
        with TestClient(self.probe) as client:
            allowed = client.get(f"/api/v1/documents/{self.direct_a.id}")
            denied = client.get(f"/api/v1/documents/{self.direct_b.id}")
            unresolved = client.get(f"/api/v1/documents/{self.mixed.id}")
            unknown = client.get("/api/v1/documents/2147483647")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(denied.status_code, 404)
        self.assertEqual(unresolved.status_code, 404)
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(denied.json(), unknown.json())
        self.assertEqual(unresolved.json(), unknown.json())

    def test_scope_precedes_limit_and_admin_user_keep_global_results(self) -> None:
        external = self.service(self.external).search(
            query=self.term,
            types=("document",),
            semantic=False,
            limit=1,
        )
        self.assertEqual(len(external.items), 1)
        self.assertIn(
            external.items[0].id,
            {self.direct_a.id, self.project_doc_a.id, self.inspection_doc_a.id},
        )
        all_ids = {
            self.direct_a.id,
            self.project_doc_a.id,
            self.inspection_doc_a.id,
            self.direct_b.id,
            self.project_doc_b.id,
            self.inspection_doc_b.id,
            self.unowned.id,
            self.mixed.id,
        }
        for viewer in (self.admin, self.user):
            ids = {
                item.id
                for item in self.service(viewer).search(
                    query=self.term,
                    types=("document",),
                    semantic=False,
                    limit=50,
                ).items
            }
            self.assertEqual(ids, all_ids)


if __name__ == "__main__":
    unittest.main()
