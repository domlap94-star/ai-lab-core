"""Controlled local-model smoke for CHUNK 12 (synthetic rows, full rollback)."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from time import perf_counter
from sqlalchemy.orm import Session

from app.database.engine import engine
from app.models.client import Client
from app.models.document import Document
from app.models.inspection import Inspection
from app.models.project import Project
from app.models.user import User
from app.services.client_knowledge_service import ClientKnowledgeContextService
from app.services.semantic_search_service import SemanticSearchService


class _NoVectors:
    def search(self, **kwargs):
        return []


async def _run(db: Session, client: Client) -> None:
    service = ClientKnowledgeContextService(db, semantic_service=_NoVectors())
    questions = (
        ("Jaki jest telefon klienta?", "500", "client"),
        ("Jakie realizacje ma ten klient?", None, "project"),
        ("Kiedy była ostatnia wizja lokalna?", None, "inspection"),
        ("Czy mamy dokument dotyczący stabilizacji fundamentu?", None, "document"),
        ("Jaki jest kolor dachu klienta?", "nie znalaz", None),
    )
    timings: list[float] = []
    for question, marker, expected_type in questions:
        started = perf_counter()
        result = await service.ask(client_id=client.id, question=question)
        timings.append((perf_counter() - started) * 1000)
        if marker is not None and marker.casefold() not in result.answer.casefold():
            raise AssertionError(f"Answer is not factual for controlled question: {question}")
        if expected_type is not None and not any(
            source.source_type == expected_type for source in result.sources
        ):
            raise AssertionError(f"Expected source type is missing: {expected_type}")
        valid = {
            (source.source_type, source.source_id)
            for source in result.sources
        }
        if len(valid) != len(result.sources):
            raise AssertionError("Duplicate or invalid source citation")
        if any(source.source_type not in {"client", "project", "inspection", "document", "email", "timeline"} for source in result.sources):
            raise AssertionError("Unknown source type")
    semantic_started = perf_counter()
    SemanticSearchService().search(
        query="stabilizacja fundamentu",
        client_id=client.id,
        limit=5,
        create_collection_if_missing=False,
    )
    semantic_ms = (perf_counter() - semantic_started) * 1000
    print(
        "timings_ms: "
        f"structured={timings[0]:.1f}, "
        f"projects={timings[1]:.1f}, "
        f"inspection={timings[2]:.1f}, "
        f"document_lexical={timings[3]:.1f}, "
        f"generation_total={timings[4]:.1f}, "
        f"semantic={semantic_ms:.1f}"
    )


def main() -> None:
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
    try:
        actor = db.query(User).filter(User.is_active.is_(True)).first()
        if actor is None:
            raise AssertionError("No active test actor")
        client = Client(
            client_type="company",
            name="Synthetic Chunk Twelve",
            primary_phone="+48 500 600 700",
            country_code="PL",
        )
        db.add(client)
        db.flush()
        project = Project(
            client_id=client.id,
            name="Hala testowa",
            description="Stabilizacja fundamentu hali.",
            status="active",
            created_by_user_id=actor.id,
        )
        db.add(project)
        db.flush()
        db.add(
            Inspection(
                project_id=project.id,
                client_id=client.id,
                title="Wizja hali",
                status="completed",
                scheduled_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                created_by_user_id=actor.id,
            )
        )
        db.add(
            Document(
                filename="synthetic-foundation.pdf",
                original_filename="Dokument stabilizacji fundamentu.pdf",
                content_type="application/pdf",
                file_size=100,
                source_type="manual_upload",
                client_id=client.id,
                extracted_text="Dokument opisuje stabilizację fundamentu hali.",
                processing_status="processed",
                metadata_status="processed",
                match_status="matched",
            )
        )
        db.flush()
        asyncio.run(_run(db, client))
        print("CHUNK 12 local LLM E2E: 5/5 PASS; durable writes: 0")
    finally:
        db.close()
        transaction.rollback()
        connection.close()


if __name__ == "__main__":
    main()
