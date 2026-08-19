from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Literal, Type

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from app.models.document_asset import DocumentAsset
from app.repositories.document_repository import DocumentRepository
from app.schemas.agent import AgentSource
from app.services.business_analytics_service import BusinessAnalyticsService
from app.services.client_email_service import ClientEmailService
from app.services.client_service import ClientService
from app.services.document_read_service import DocumentReadService
from app.services.global_search_service import GlobalSearchService
from app.services.inspection_service import InspectionService
from app.services.project_service import ProjectService
from app.services.timeline_service import TimelineService


class ToolDenied(RuntimeError): pass
class ScopeViolation(RuntimeError): pass


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchArgs(_Args):
    query: str = Field(min_length=2, max_length=200)
    limit: int = Field(default=10, ge=1, le=20)


class IdArgs(_Args):
    id: int = Field(gt=0)


class ClientIdArgs(_Args):
    client_id: int = Field(gt=0)


class TimelineArgs(ClientIdArgs):
    limit: int = Field(default=10, ge=1, le=10)


class DocumentSearchArgs(SearchArgs):
    client_id: int | None = Field(default=None, gt=0)


class EntitySearchArgs(SearchArgs):
    client_id: int | None = Field(default=None, gt=0)


class EmailSearchArgs(SearchArgs):
    client_id: int | None = Field(default=None, gt=0)


class EmailMetadataArgs(_Args):
    email_id: int = Field(gt=0)
    client_id: int = Field(gt=0)


class GlobalSearchArgs(SearchArgs):
    types: list[Literal["client", "candidate", "email", "document", "inspection", "project"]] = Field(default_factory=list, max_length=6)


class AnalyticsArgs(_Args):
    question: str = Field(min_length=2, max_length=500)


@dataclass(frozen=True)
class AgentToolDefinition:
    name: str
    description: str
    args_schema: Type[BaseModel]
    executor: Callable[[BaseModel], "AgentToolResult"]
    risk_level: Literal["READ_ONLY"] = "READ_ONLY"
    read_only: bool = True
    timeout_seconds: int = 5
    max_results: int = 20


@dataclass
class AgentToolResult:
    data: dict[str, Any]
    sources: list[AgentSource]
    coverage: dict[str, int]
    limitations: list[str]


class AgentToolRegistry:
    """Closed registry over existing read services. No arbitrary callable is exposed."""

    def __init__(self, db: Session, *, client_id: int | None = None, inspection_id: int | None = None):
        self.db, self.client_id, self.inspection_id = db, client_id, inspection_id
        self.clients = ClientService(db)
        self.documents = DocumentReadService(db)
        self.document_repo = DocumentRepository(db)
        self.inspections = InspectionService(db)
        self.projects = ProjectService(db)
        self.timeline = TimelineService(db)
        self.emails = ClientEmailService(db)
        self.search = GlobalSearchService(db)
        self.analytics = BusinessAnalyticsService(db)
        self._tools = self._build()

    @property
    def definitions(self) -> dict[str, AgentToolDefinition]:
        return dict(self._tools)

    def execute(self, name: str, arguments: dict[str, Any]) -> AgentToolResult:
        definition = self._tools.get(name)
        if definition is None:
            raise ToolDenied("TOOL_NOT_ALLOWED")
        if self.client_id is not None and name == "business_analytics":
            raise ScopeViolation("SCOPE_VIOLATION")
        try:
            parsed = definition.args_schema.model_validate(arguments)
        except ValidationError as error:
            raise ToolDenied("INVALID_TOOL_ARGUMENTS") from error
        self._enforce_scope(parsed)
        return definition.executor(parsed)

    def _enforce_scope(self, args: BaseModel) -> None:
        values = args.model_dump()
        requested_client = values.get("client_id")
        if self.client_id is not None and requested_client not in (None, self.client_id):
            raise ScopeViolation("SCOPE_VIOLATION")
        if self.client_id is not None and "client_id" in values and requested_client is None:
            setattr(args, "client_id", self.client_id)
        entity_id = values.get("id")
        if self.client_id is not None and entity_id is not None:
            if isinstance(args, IdArgs):
                # Entity ownership is checked by each typed get executor.
                return

    def _build(self) -> dict[str, AgentToolDefinition]:
        definitions = [
            AgentToolDefinition("search_clients", "Znajdź klientów.", SearchArgs, self._search_clients),
            AgentToolDefinition("get_client", "Pobierz klienta.", IdArgs, self._get_client),
            AgentToolDefinition("get_client_contacts", "Pobierz kontakty klienta.", ClientIdArgs, self._get_contacts),
            AgentToolDefinition("get_client_timeline", "Pobierz ostatnie zdarzenia klienta.", TimelineArgs, self._get_timeline),
            AgentToolDefinition("search_documents", "Znajdź dokumenty.", DocumentSearchArgs, self._search_documents, timeout_seconds=10, max_results=20),
            AgentToolDefinition("get_document_summary", "Pobierz podsumowanie dokumentu.", IdArgs, self._get_document),
            AgentToolDefinition("get_document_pages", "Pobierz tekst maksymalnie 8 stron.", IdArgs, self._get_pages, max_results=8),
            AgentToolDefinition("get_visual_analysis", "Odczytaj istniejącą analizę Vision.", IdArgs, self._get_visual, max_results=8),
            AgentToolDefinition("search_inspections", "Znajdź wizje lokalne.", EntitySearchArgs, self._search_inspections),
            AgentToolDefinition("get_inspection", "Pobierz wizję lokalną.", IdArgs, self._get_inspection),
            AgentToolDefinition("search_projects", "Znajdź realizacje legacy.", EntitySearchArgs, self._search_projects),
            AgentToolDefinition("get_project", "Pobierz realizację legacy.", IdArgs, self._get_project),
            AgentToolDefinition("search_emails", "Znajdź metadane e-maili.", EmailSearchArgs, self._search_emails, timeout_seconds=10),
            AgentToolDefinition("get_email_metadata", "Pobierz bounded metadane e-maila.", EmailMetadataArgs, self._get_email),
            AgentToolDefinition("global_search", "Przeszukaj CRM.", GlobalSearchArgs, self._global_search, timeout_seconds=10),
            AgentToolDefinition("business_analytics", "Wykonaj deterministyczną analizę biznesową.", AnalyticsArgs, self._analytics),
        ]
        return {item.name: item for item in definitions}

    @staticmethod
    def _source(kind: str, entity_id: int | None, title: str, route: str | None, snippet: str = "", date=None) -> AgentSource:
        return AgentSource(source_type=kind, source_id=entity_id, title=title[:255], route=route, snippet=" ".join((snippet or "").split())[:600], date=date)

    def _require_client(self, client_id: int) -> None:
        if self.client_id is not None and client_id != self.client_id:
            raise ScopeViolation("SCOPE_VIOLATION")

    def _search_clients(self, args: SearchArgs) -> AgentToolResult:
        if self.client_id is not None:
            scoped = self.clients.get_client(self.client_id)
            items = [scoped] if args.query.casefold() in scoped.name.casefold() else []
        else:
            items = self.clients.get_clients(search=args.query, skip=0, limit=args.limit).items
        rows = [
            {
                "id": x.id,
                "name": x.name,
                "city": x.city,
                "workflow_status": getattr(x, "workflow_status", "untouched"),
                "workflow_status_label": getattr(
                    x,
                    "workflow_status_label",
                    "Brak modyfikacji",
                ),
            }
            for x in items
        ]
        sources = [self._source("client", x.id, x.name, f"/clients/{x.id}", x.city or "", x.updated_at) for x in items]
        return AgentToolResult({"clients": rows}, sources, {"clients": len(rows)}, [])

    def _get_client(self, args: IdArgs) -> AgentToolResult:
        self._require_client(args.id)
        x = self.clients.get_client(args.id)
        address = " ".join(filter(None, [x.street, x.building_number, x.postal_code, x.city]))
        data = {
            "id": x.id,
            "name": x.name,
            "type": x.client_type,
            "address": address,
            "created_at": x.created_at.isoformat(),
            "workflow_status": getattr(x, "workflow_status", "untouched"),
            "workflow_status_label": getattr(
                x,
                "workflow_status_label",
                "Brak modyfikacji",
            ),
        }
        return AgentToolResult(data, [self._source("client", x.id, x.name, f"/clients/{x.id}", address, x.updated_at)], {"clients": 1}, [])

    def _get_contacts(self, args: ClientIdArgs) -> AgentToolResult:
        self._require_client(args.client_id)
        x = self.clients.get_client(args.client_id)
        contacts = [{"type": c.kind, "value": c.value, "primary": c.is_primary, "origin": c.origin} for c in (x.emails + x.phones)[:20]]
        return AgentToolResult({"contacts": contacts}, [self._source("client", x.id, x.name, f"/clients/{x.id}", f"Kontakty: {len(contacts)}")], {"contacts": len(contacts)}, [])

    def _get_timeline(self, args: TimelineArgs) -> AgentToolResult:
        self._require_client(args.client_id)
        page = self.timeline.get_client_timeline(client_id=args.client_id, skip=0, limit=args.limit)
        rows, sources = [], []
        for x in page.items:
            rows.append({"date": x.occurred_at.isoformat(), "type": x.event_type, "title": x.title, "summary": (x.summary or "")[:300]})
            route = f"/clients/{args.client_id}/timeline"
            sources.append(self._source(x.source_type, int(x.source_id) if str(x.source_id).isdigit() else None, x.title, route, x.summary or "", x.occurred_at))
        return AgentToolResult({"events": rows}, sources, {"timeline_events": len(rows)}, [])

    def _search_documents(self, args: DocumentSearchArgs) -> AgentToolResult:
        client_id = args.client_id or self.client_id
        page = self.search.search(query=args.query, types=("document",), limit=args.limit, semantic=True)
        items = [x for x in page.items if client_id is None or x.client_id == client_id][:args.limit]
        sources = [self._source("document", x.id, x.title, x.route, x.snippet or x.subtitle or "", x.occurred_at) for x in items]
        limits = ["Wyszukiwanie semantyczne niedostępne; użyto wyników tekstowych."] if page.semantic_status == "unavailable" else []
        return AgentToolResult({"documents": [x.model_dump(mode="json") for x in items]}, sources, {"documents": len(items)}, limits)

    def _document(self, document_id: int):
        x = self.document_repo.get(document_id)
        if x is None or (self.client_id is not None and x.client_id != self.client_id):
            raise ScopeViolation("SCOPE_VIOLATION")
        if self.inspection_id is not None and x.inspection_id != self.inspection_id:
            raise ScopeViolation("SCOPE_VIOLATION")
        return x

    def _get_document(self, args: IdArgs) -> AgentToolResult:
        x = self._document(args.id)
        text = " ".join((x.extracted_text or "").split())[:1200]
        name = x.original_filename or x.filename
        data = {"id": x.id, "filename": name, "content_type": x.content_type, "created_at": x.created_at.isoformat(), "page_count": len(x.pages), "vision_status": x.vision_status, "text_snippet": text}
        return AgentToolResult(data, [self._source("document", x.id, name, f"/documents/{x.id}", text, x.created_at)], {"documents": 1}, [])

    def _get_pages(self, args: IdArgs) -> AgentToolResult:
        x = self._document(args.id)
        pages = self.document_repo.get_pages(x.id)[:8]
        rows = [{"page": p.page_number, "text": " ".join((p.extracted_text or p.ocr_text or "").split())[:800], "vision_status": p.vision_status} for p in pages]
        sources = [self._source("document", x.id, f"{x.original_filename or x.filename} — strona {p.page_number}", f"/documents/{x.id}", rows[i]["text"], p.updated_at) for i, p in enumerate(pages)]
        return AgentToolResult({"pages": rows}, sources, {"document_pages": len(rows)}, [])

    def _get_visual(self, args: IdArgs) -> AgentToolResult:
        x = self._document(args.id)
        values, sources = [], []
        candidates = list(x.pages[:8]) + list(x.assets[:8])
        for item in candidates:
            if not item.vision_analysis:
                continue
            try: parsed = json.loads(item.vision_analysis)
            except (TypeError, json.JSONDecodeError): continue
            bounded = {key: parsed.get(key, [])[:12] for key in ("observations", "possible_interpretations", "uncertainties", "visible_text")}
            values.append(bounded)
            label = f"strona {item.page_number}" if hasattr(item, "page_number") and item.page_number else f"asset {getattr(item, 'asset_index', '?')}"
            sources.append(self._source("document", x.id, f"{x.original_filename or x.filename} — {label}", f"/documents/{x.id}", "Zweryfikowana analiza wizualna"))
        limitation = [] if values else ["Analiza wizualna nie jest jeszcze dostępna dla tego źródła."]
        return AgentToolResult({"visual_results": values}, sources, {"visual_results": len(values)}, limitation)

    def _search_inspections(self, args: EntitySearchArgs) -> AgentToolResult:
        page = self.inspections.get_page(search=args.query, project_id=None, client_id=args.client_id or self.client_id, status=None, date_from=None, date_to=None, skip=0, limit=args.limit)
        sources = [self._source("inspection", x.id, x.title, f"/inspections/{x.id}", x.notes or "", x.scheduled_at or x.created_at) for x in page.items]
        return AgentToolResult({"inspections": [{"id": x.id, "title": x.title, "status": x.status} for x in page.items]}, sources, {"inspections": len(sources)}, [])

    def _get_inspection(self, args: IdArgs) -> AgentToolResult:
        x = self.inspections.get(args.id); self._require_client(x.client_id)
        if self.inspection_id is not None and x.id != self.inspection_id: raise ScopeViolation("SCOPE_VIOLATION")
        data = {"id": x.id, "status": x.status, "scheduled_at": x.scheduled_at.isoformat() if x.scheduled_at else None, "notes": (x.notes or "")[:1000], "location": {"latitude": x.latitude, "longitude": x.longitude, "accuracy_m": x.location_accuracy_m}, "document_count": len(x.documents)}
        return AgentToolResult(data, [self._source("inspection", x.id, x.title, f"/inspections/{x.id}", x.notes or "", x.updated_at)], {"inspections": 1}, [])

    def _search_projects(self, args: EntitySearchArgs) -> AgentToolResult:
        page = self.projects.get_page(search=args.query, client_id=args.client_id or self.client_id, status=None, skip=0, limit=args.limit)
        sources = [self._source("project", x.id, x.name, f"/projects/{x.id}", x.description or "", x.updated_at) for x in page.items]
        return AgentToolResult({"projects": [{"id": x.id, "name": x.name, "status": x.status} for x in page.items]}, sources, {"projects": len(sources)}, [])

    def _get_project(self, args: IdArgs) -> AgentToolResult:
        x = self.projects.get(args.id); self._require_client(x.client_id)
        return AgentToolResult({"id": x.id, "name": x.name, "status": x.status, "description": (x.description or "")[:1000]}, [self._source("project", x.id, x.name, f"/projects/{x.id}", x.description or "", x.updated_at)], {"projects": 1}, [])

    def _search_emails(self, args: EmailSearchArgs) -> AgentToolResult:
        client_id = args.client_id or self.client_id
        page = self.search.search(query=args.query, types=("email",), limit=args.limit, semantic=False)
        items = [x for x in page.items if client_id is None or x.client_id == client_id][:args.limit]
        sources = [self._source("email", x.id, x.title, x.route, x.snippet or x.subtitle or "", x.occurred_at) for x in items]
        return AgentToolResult({"emails": [x.model_dump(mode="json") for x in items]}, sources, {"emails": len(items)}, [])

    def _get_email(self, args: EmailMetadataArgs) -> AgentToolResult:
        self._require_client(args.client_id)
        page = self.emails.get_emails(client_id=args.client_id, source_id=args.email_id, skip=0, limit=1)
        if not page.items: raise ScopeViolation("SCOPE_VIOLATION")
        x = page.items[0]
        data = {"id": x.id, "subject": x.subject, "sender": x.from_address, "recipients": x.to_addresses[:10], "date": x.message_at.isoformat() if x.message_at else None, "snippet": " ".join((x.body_text or "").split())[:600], "attachments": x.attachment_count}
        return AgentToolResult(data, [self._source("email", x.id, x.subject or "E-mail", f"/clients/{args.client_id}?email_source_id={x.id}", data["snippet"], x.message_at)], {"emails": 1}, [])

    def _global_search(self, args: GlobalSearchArgs) -> AgentToolResult:
        allowed = {"client", "candidate", "email", "document", "inspection", "project"}
        types = tuple(x for x in args.types if x in allowed) or tuple(allowed)
        page = self.search.search(query=args.query, types=types, limit=args.limit, semantic=True)
        items = [
            x for x in page.items
            if self.client_id is None
            or x.client_id == self.client_id
            or (x.type == "client" and x.id == self.client_id)
        ][:args.limit]
        sources = [self._source(x.type, x.id, x.title, x.route, x.snippet or x.subtitle or "", x.occurred_at) for x in items]
        limits = ["Wyszukiwanie semantyczne niedostępne; zachowano wyniki strukturalne i tekstowe."] if page.semantic_status == "unavailable" else []
        return AgentToolResult({"results": [x.model_dump(mode="json") for x in items]}, sources, {"search_results": len(items)}, limits)

    def _analytics(self, args: AnalyticsArgs) -> AgentToolResult:
        result = self.analytics.direct_answer(args.question)
        if result is None: return AgentToolResult({"answer": None}, [], {}, ["Brak deterministycznej analizy dla tego pytania."])
        sources = [AgentSource(source_type=x.source_type, source_id=x.source_id, title=x.title, date=x.date, route=x.route, snippet=x.snippet) for x in result.sources]
        return AgentToolResult({"answer": result.answer}, sources, {"analytics": 1}, [])
