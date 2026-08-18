"""Controlled CHUNK 16 planner smoke using the local model.

All database writes, including AgentExecution rows, are rolled back.
"""
from __future__ import annotations

import asyncio
import os
import statistics
from time import perf_counter

from sqlalchemy.orm import Session

from app.database.engine import engine
from app.models.user import User
from app.schemas.agent import AgentSource
from app.services.agent_service import AgentService
from app.services.agent_tool_registry import AgentToolRegistry, AgentToolResult


class _ControlledRegistry(AgentToolRegistry):
    """Keep the real allowlist/schemas while returning synthetic bounded data."""

    def execute(self, name: str, arguments: dict) -> AgentToolResult:
        definition = self.definitions.get(name)
        if definition is None:
            return super().execute(name, arguments)
        definition.args_schema.model_validate(arguments)
        return AgentToolResult(
            data={"summary": f"Kontrolowany wynik narzędzia {name}."},
            sources=[
                AgentSource(
                    source_type="analytics",
                    source_id=sorted(self.definitions).index(name) + 1,
                    title=f"Kontrolowane źródło {name}",
                    route="/ai?mode=agent",
                    snippet="Syntetyczny, ograniczony wynik bez danych klienta.",
                )
            ],
            coverage={name: 1},
            limitations=[],
        )


async def _run(db: Session, user_id: int) -> None:
    cases = (
        "Znajdź klienta o nazwie Kontrolowany.",
        "Podsumuj dane klienta o identyfikatorze 1.",
        "Pokaż ostatnie zdarzenia na osi czasu klienta 1.",
        "Znajdź najnowsze dokumenty dotyczące fundamentów.",
        "Pokaż strony dokumentu 1.",
        "Sprawdź zapisaną analizę wizualną dokumentu 1.",
        "Znajdź zaplanowane wizje lokalne.",
        "Znajdź aktywne projekty legacy.",
        "Znajdź najnowsze wiadomości e-mail dotyczące wizji.",
        "Wyszukaj globalnie hasło stabilizacja gruntu.",
        "Podaj deterministyczne statystyki klientów wymagających uwagi.",
        "Zbierz informacje o kliencie i jego najnowszej aktywności.",
    )
    selected = os.environ.get("AGENT_E2E_CASE")
    if selected:
        cases = (cases[int(selected) - 1],)
    durations: list[float] = []
    for index, question in enumerate(cases, 1):
        started = perf_counter()
        result = await AgentService(db, registry_factory=_ControlledRegistry).ask(
            question=question,
            user_id=user_id,
            client_id=None,
            inspection_id=None,
            conversation=[],
        )
        duration = (perf_counter() - started) * 1000
        durations.append(duration)
        if result.status != "completed" or not result.answer:
            raise AssertionError(f"Case {index}: incomplete response")
        if len(result.tool_trace) > 8:
            raise AssertionError(f"Case {index}: tool limit exceeded")
        if not result.sources:
            raise AssertionError(f"Case {index}: grounded response has no source")
        if any(source.source_type != "analytics" for source in result.sources):
            raise AssertionError(f"Case {index}: fabricated source exposed")
        print(
            f"case={index} tools={[item.name for item in result.tool_trace]} "
            f"sources={len(result.sources)} duration_ms={duration:.1f}"
        )
    ordered = sorted(durations)
    p50 = statistics.median(ordered)
    print(
        f"CHUNK 16 local LLM E2E: {len(cases)}/{len(cases)} PASS; durable writes: 0; "
        f"total_p50_ms={p50:.1f}; total_max_ms={max(ordered):.1f}"
    )


def main() -> None:
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        user = db.query(User).filter(User.is_active.is_(True)).first()
        if user is None:
            raise AssertionError("Controlled active user is unavailable")
        asyncio.run(_run(db, user.id))
    finally:
        db.close()
        transaction.rollback()
        connection.close()


if __name__ == "__main__":
    main()
