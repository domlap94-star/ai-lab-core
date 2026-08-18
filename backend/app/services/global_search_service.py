from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Iterable

from sqlalchemy import Text, and_, cast, func, literal, or_
from sqlalchemy.orm import Session, selectinload

from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_address import ClientAddress
from app.models.client_candidate import ClientCandidate
from app.models.client_contact_point import ClientContactPoint
from app.models.document import Document
from app.models.inspection import Inspection
from app.models.project import Project
from app.repositories.client_email_repository import LINKED_CANDIDATE_STATUSES
from app.schemas.search import GlobalSearchPage, GlobalSearchResult
from app.services.client_email_service import ClientEmailService
from app.services.semantic_search_service import SemanticSearchService


SEARCH_TYPES = (
    "client",
    "project",
    "inspection",
    "document",
    "email",
    "candidate",
)
SNIPPET_LIMIT = 260


class SearchTypeError(ValueError):
    pass


@dataclass(frozen=True)
class _TextQuery:
    value: str
    folded: str
    digits: str
    phone_digits: str


class GlobalSearchService:
    """Bounded, read-only aggregation of structured and semantic matches."""

    _type_order = {name: index for index, name in enumerate(SEARCH_TYPES)}

    def __init__(
        self,
        db: Session,
        *,
        semantic_service: SemanticSearchService | None = None,
    ) -> None:
        self.db = db
        self.semantic_service = semantic_service or SemanticSearchService()
        self.email_projection = ClientEmailService(db)

    @staticmethod
    def parse_types(value: str | None) -> tuple[str, ...]:
        if value is None or not value.strip():
            return SEARCH_TYPES
        requested = tuple(
            dict.fromkeys(
                item.strip().casefold()
                for item in value.split(",")
                if item.strip()
            )
        )
        invalid = [item for item in requested if item not in SEARCH_TYPES]
        if invalid:
            raise SearchTypeError(
                "Unsupported search type: " + ", ".join(invalid)
            )
        if not requested:
            raise SearchTypeError("At least one search type is required")
        return requested

    def search(
        self,
        *,
        query: str,
        types: Iterable[str] = SEARCH_TYPES,
        skip: int = 0,
        limit: int = 25,
        semantic: bool = True,
    ) -> GlobalSearchPage:
        normalized = " ".join(query.split())
        if len(normalized) < 2:
            raise ValueError("Search query must contain at least 2 characters")
        q = _TextQuery(
            value=normalized,
            folded=normalized.casefold(),
            digits=re.sub(r"\D", "", normalized),
            phone_digits=self._local_phone_digits(normalized),
        )
        requested = tuple(types)
        fetch_limit = min(skip + limit + 1, 551)
        results: list[GlobalSearchResult] = []

        loaders = {
            "client": self._clients,
            "project": self._projects,
            "inspection": self._inspections,
            "document": self._documents,
            "email": self._emails,
            "candidate": self._candidates,
        }
        for entity_type in requested:
            results.extend(loaders[entity_type](q, fetch_limit))

        semantic_status = "not_requested"
        if semantic and "document" in requested and self._is_semantic_query(q):
            try:
                results.extend(
                    self._semantic_documents(q, min(fetch_limit, 30))
                )
                semantic_status = "available"
            except Exception:
                # Optional Qdrant/Ollama failures never hide SQL results.
                semantic_status = "unavailable"

        ordered = sorted(self._merge(results), key=self._sort_key)
        return GlobalSearchPage(
            items=ordered[skip : skip + limit],
            skip=skip,
            limit=limit,
            has_more=len(ordered) > skip + limit,
            semantic_status=semantic_status,
        )

    def _clients(self, q: _TextQuery, limit: int) -> list[GlobalSearchResult]:
        pattern = f"%{q.value}%"
        conditions = [
            Client.name.ilike(pattern),
            Client.legal_name.ilike(pattern),
            Client.tax_id.ilike(pattern),
            Client.primary_email.ilike(pattern),
            Client.primary_phone.ilike(pattern),
            Client.street.ilike(pattern),
            Client.building_number.ilike(pattern),
            Client.postal_code.ilike(pattern),
            Client.city.ilike(pattern),
            Client.notes.ilike(pattern),
            Client.contact_points.any(
                and_(
                    ClientContactPoint.deleted_at.is_(None),
                    ClientContactPoint.normalized_value.ilike(pattern),
                )
            ),
            Client.address_records.any(
                and_(
                    ClientAddress.deleted_at.is_(None),
                    or_(
                        ClientAddress.street.ilike(pattern),
                        ClientAddress.building_number.ilike(pattern),
                        ClientAddress.postal_code.ilike(pattern),
                        ClientAddress.city.ilike(pattern),
                    ),
                )
            ),
        ]
        if q.digits:
            phone_pattern = f"%{q.phone_digits or q.digits}%"
            conditions.extend(
                [
                    func.regexp_replace(
                        Client.primary_phone, r"[^0-9]", "", "g"
                    ).ilike(phone_pattern),
                    func.regexp_replace(
                        Client.tax_id, r"[^0-9]", "", "g"
                    ).ilike(f"%{q.digits}%"),
                    Client.contact_points.any(
                        and_(
                            ClientContactPoint.deleted_at.is_(None),
                            ClientContactPoint.kind == "phone",
                            func.regexp_replace(
                                ClientContactPoint.normalized_value,
                                r"[^0-9]",
                                "",
                                "g",
                            ).ilike(phone_pattern),
                        )
                    ),
                ]
            )
        rows = (
            self.db.query(Client)
            .options(
                selectinload(Client.contact_points),
                selectinload(Client.address_records),
            )
            .filter(Client.deleted_at.is_(None), or_(*conditions))
            .order_by(Client.updated_at.desc(), Client.id.desc())
            .limit(limit)
            .all()
        )
        return [self._client_result(row, q) for row in rows]

    def _client_result(self, row: Client, q: _TextQuery) -> GlobalSearchResult:
        emails = [row.primary_email, *(item.value for item in row.emails)]
        phones = [row.primary_phone, *(item.value for item in row.phones)]
        reasons: list[str] = []
        score = 0.0
        if self._exact(q.folded, [row.name, row.legal_name]):
            reasons.append("name")
            score = 1.0
        elif self._contains(q.folded, [row.name, row.legal_name]):
            reasons.append("name")
            score = 0.88
        if self._exact(q.folded, emails):
            reasons.append("email")
            score = max(score, 1.0)
        elif self._contains(q.folded, emails):
            reasons.append("email")
            score = max(score, 0.9)
        if q.phone_digits and any(
            self._local_phone_digits(value) == q.phone_digits
            for value in phones
            if value
        ):
            reasons.append("phone")
            score = max(score, 1.0)
        elif q.digits and any(
            q.phone_digits in self._local_phone_digits(value)
            for value in phones
            if value
        ):
            reasons.append("phone")
            score = max(score, 0.9)
        if q.digits and row.tax_id and re.sub(r"\D", "", row.tax_id) == q.digits:
            reasons.append("nip")
            score = max(score, 1.0)
        elif self._contains(q.folded, [row.tax_id]):
            reasons.append("nip")
            score = max(score, 0.9)
        addresses = [
            row.street,
            row.building_number,
            row.postal_code,
            row.city,
            *(
                part
                for item in row.addresses
                for part in (
                    item.street,
                    item.building_number,
                    item.postal_code,
                    item.city,
                )
            ),
        ]
        if self._contains(q.folded, addresses):
            reasons.append("address")
            score = max(score, 0.82)
        if self._contains(q.folded, [row.notes]):
            reasons.append("notes")
            score = max(score, 0.7)
        return self._result(
            type="client",
            id=row.id,
            title=row.name,
            subtitle=row.legal_name or self._address(addresses),
            snippet=self._matching_snippet(
                q.folded, [row.notes, *emails, *phones]
            ),
            score=score,
            reasons=reasons,
            occurred_at=row.updated_at,
            client_id=row.id,
            route=f"/clients/{row.id}",
        )

    def _projects(self, q: _TextQuery, limit: int) -> list[GlobalSearchResult]:
        pattern = f"%{q.value}%"
        rows = (
            self.db.query(Project, Client.name.label("client_name"))
            .join(Client, Client.id == Project.client_id)
            .filter(
                Project.deleted_at.is_(None),
                Client.deleted_at.is_(None),
                or_(
                    Project.name.ilike(pattern),
                    Project.description.ilike(pattern),
                    Project.status.ilike(pattern),
                    Project.street.ilike(pattern),
                    Project.building_number.ilike(pattern),
                    Project.postal_code.ilike(pattern),
                    Project.city.ilike(pattern),
                    Client.name.ilike(pattern),
                ),
            )
            .order_by(Project.updated_at.desc(), Project.id.desc())
            .limit(limit)
            .all()
        )
        results = []
        for project, client_name in rows:
            reasons: list[str] = []
            score = 0.0
            if self._exact(q.folded, [project.name]):
                reasons.append("project")
                score = 0.98
            elif self._contains(q.folded, [project.name, client_name]):
                reasons.append("project")
                score = 0.84
            if self._contains(
                q.folded,
                [project.street, project.building_number, project.postal_code, project.city],
            ):
                reasons.append("address")
                score = max(score, 0.8)
            if self._contains(q.folded, [project.description]):
                reasons.append("notes")
                score = max(score, 0.7)
            if self._contains(q.folded, [project.status]):
                reasons.append("status")
                score = max(score, 0.72)
            results.append(
                self._result(
                    type="project",
                    id=project.id,
                    title=project.name,
                    subtitle=f"Klient: {client_name}",
                    snippet=self._matching_snippet(
                        q.folded, [project.description, project.street, project.city]
                    ),
                    score=score,
                    reasons=reasons,
                    occurred_at=project.updated_at,
                    client_id=project.client_id,
                    project_id=project.id,
                    route=f"/projects/{project.id}",
                )
            )
        return results

    def _inspections(self, q: _TextQuery, limit: int) -> list[GlobalSearchResult]:
        pattern = f"%{q.value}%"
        rows = (
            self.db.query(Inspection, Project.name, Client.name)
            .join(Project, Project.id == Inspection.project_id)
            .join(Client, Client.id == Inspection.client_id)
            .filter(
                Inspection.deleted_at.is_(None),
                Project.deleted_at.is_(None),
                Client.deleted_at.is_(None),
                or_(
                    Inspection.title.ilike(pattern),
                    Inspection.notes.ilike(pattern),
                    Inspection.status.ilike(pattern),
                    Project.name.ilike(pattern),
                    Project.street.ilike(pattern),
                    Project.city.ilike(pattern),
                    Client.name.ilike(pattern),
                ),
            )
            .order_by(Inspection.updated_at.desc(), Inspection.id.desc())
            .limit(limit)
            .all()
        )
        results = []
        for inspection, project_name, client_name in rows:
            reasons: list[str] = []
            score = 0.0
            if self._exact(q.folded, [inspection.title]):
                reasons.append("inspection")
                score = 0.98
            elif self._contains(q.folded, [inspection.title, project_name, client_name]):
                reasons.append("inspection")
                score = 0.84
            if self._contains(q.folded, [inspection.notes]):
                reasons.append("notes")
                score = max(score, 0.7)
            if self._contains(q.folded, [inspection.status]):
                reasons.append("status")
                score = max(score, 0.72)
            if self._contains(q.folded, [project_name]):
                reasons.append("project")
                score = max(score, 0.8)
            results.append(
                self._result(
                    type="inspection",
                    id=inspection.id,
                    title=inspection.title,
                    subtitle=f"{client_name} · {project_name}",
                    snippet=self._matching_snippet(q.folded, [inspection.notes]),
                    score=score,
                    reasons=reasons,
                    occurred_at=inspection.scheduled_at or inspection.updated_at,
                    client_id=inspection.client_id,
                    project_id=inspection.project_id,
                    inspection_id=inspection.id,
                    route=f"/inspections/{inspection.id}",
                )
            )
        return results

    def _documents(self, q: _TextQuery, limit: int) -> list[GlobalSearchResult]:
        pattern = f"%{q.value}%"
        rows = (
            self.db.query(Document, Client.name, Project.name, Inspection.title)
            .outerjoin(Client, Client.id == Document.client_id)
            .outerjoin(Project, Project.id == Document.project_id)
            .outerjoin(Inspection, Inspection.id == Document.inspection_id)
            .filter(
                or_(
                    Document.filename.ilike(pattern),
                    Document.original_filename.ilike(pattern),
                    Document.archive_member_path.ilike(pattern),
                    Document.extracted_text.ilike(pattern),
                    cast(Document.metadata_normalized, Text).ilike(pattern),
                    Client.name.ilike(pattern),
                    Project.name.ilike(pattern),
                    Inspection.title.ilike(pattern),
                )
            )
            .order_by(Document.updated_at.desc(), Document.id.desc())
            .limit(limit)
            .all()
        )
        results = []
        for document, client_name, project_name, inspection_title in rows:
            reasons: list[str] = []
            score = 0.0
            names = [
                document.original_filename,
                document.filename,
                document.archive_member_path,
            ]
            if self._exact(q.folded, names):
                reasons.append("filename")
                score = 0.98
            elif self._contains(q.folded, names):
                reasons.append("filename")
                score = 0.86
            if self._contains(q.folded, [document.extracted_text]):
                reasons.append("document_text")
                score = max(score, 0.72)
            if self._contains(q.folded, [client_name]):
                reasons.append("name")
                score = max(score, 0.78)
            if self._contains(q.folded, [project_name]):
                reasons.append("project")
                score = max(score, 0.78)
            if self._contains(q.folded, [inspection_title]):
                reasons.append("inspection")
                score = max(score, 0.78)
            results.append(
                self._result(
                    type="document",
                    id=document.id,
                    title=document.original_filename or document.filename,
                    subtitle=f"Klient: {client_name}" if client_name else None,
                    snippet=self._matching_snippet(q.folded, [document.extracted_text]),
                    score=score,
                    reasons=reasons,
                    occurred_at=document.captured_at or document.created_at,
                    client_id=document.client_id,
                    project_id=document.project_id,
                    inspection_id=document.inspection_id,
                    route=f"/documents?document_id={document.id}",
                )
            )
        return results

    def _emails(self, q: _TextQuery, limit: int) -> list[GlobalSearchResult]:
        payload = CandidateSource.raw_payload
        searchable = func.to_tsvector(
            "simple",
            func.coalesce(payload.op("->>")("subject"), "")
            + literal(" ")
            + func.coalesce(payload.op("->>")("Subject"), "")
            + literal(" ")
            + func.coalesce(payload.op("->>")("from"), "")
            + literal(" ")
            + func.coalesce(payload.op("->>")("From"), "")
            + literal(" ")
            + func.coalesce(payload.op("->>")("to"), "")
            + literal(" ")
            + func.coalesce(payload.op("->>")("To"), "")
            + literal(" ")
            + func.coalesce(payload.op("->>")("text"), "")
            + literal(" ")
            + func.coalesce(payload.op("->>")("textPlain"), "")
            + literal(" ")
            + func.coalesce(payload.op("->>")("snippet"), "")
            + literal(" ")
            + func.coalesce(CandidateSource.extracted_text, ""),
        )
        text_query = func.websearch_to_tsquery("simple", q.value)
        rows = (
            self.db.query(CandidateSource, ClientCandidate, Client)
            .join(ClientCandidate, ClientCandidate.id == CandidateSource.candidate_id)
            .join(Client, Client.id == ClientCandidate.matched_client_id)
            .filter(
                CandidateSource.source_type == "gmail_message",
                CandidateSource.deleted_at.is_(None),
                ClientCandidate.deleted_at.is_(None),
                Client.deleted_at.is_(None),
                ClientCandidate.status.in_(LINKED_CANDIDATE_STATUSES),
                searchable.op("@@")(text_query),
            )
            .order_by(CandidateSource.created_at.desc(), CandidateSource.id.desc())
            .limit(min(limit * 4, 551))
            .all()
        )
        results = []
        for source, candidate, client in rows:
            del candidate
            raw = source.raw_payload if isinstance(source.raw_payload, dict) else {}
            subject_value = self.email_projection._clean_string(
                raw.get("subject") or raw.get("Subject")
            )
            sender_values = [
                part
                for pair in self.email_projection._addresses(
                    raw.get("from") or raw.get("From")
                )
                for part in pair
            ]
            recipient_values = [
                part
                for pair in self.email_projection._addresses(
                    raw.get("to") or raw.get("To")
                )
                for part in pair
            ]
            body_value = self.email_projection._body_text(raw, source.extracted_text)
            reasons: list[str] = []
            score = 0.0
            if self._contains(q.folded, [subject_value]):
                reasons.append("email_subject")
                score = 0.86
            if self._contains(q.folded, [*sender_values, *recipient_values]):
                reasons.append("email")
                score = max(score, 0.9)
            if self._contains(q.folded, [body_value]):
                reasons.append("email_body")
                score = max(score, 0.7)
            if not reasons:
                continue
            direction = self.email_projection._direction(raw)
            results.append(
                self._result(
                    type="email",
                    id=source.id,
                    title=subject_value or "(bez tematu)",
                    subtitle=f"{direction} · {client.name}",
                    snippet=self._matching_snippet(
                        q.folded,
                        [body_value, *sender_values, *recipient_values],
                    ),
                    score=score,
                    reasons=reasons,
                    occurred_at=(
                        self.email_projection._parse_message_at(raw)
                        or source.created_at
                    ),
                    client_id=client.id,
                    route=f"/clients/{client.id}?email_source_id={source.id}",
                )
            )
            if len(results) >= limit:
                break
        return results

    def _candidates(self, q: _TextQuery, limit: int) -> list[GlobalSearchResult]:
        pattern = f"%{q.value}%"
        source_label = (
            self.db.query(
                CandidateSource.candidate_id.label("candidate_id"),
                func.min(CandidateSource.source_label).label("source_label"),
            )
            .filter(CandidateSource.deleted_at.is_(None))
            .group_by(CandidateSource.candidate_id)
            .subquery()
        )
        rows = (
            self.db.query(ClientCandidate, source_label.c.source_label)
            .outerjoin(source_label, source_label.c.candidate_id == ClientCandidate.id)
            .filter(
                ClientCandidate.deleted_at.is_(None),
                or_(
                    ClientCandidate.name.ilike(pattern),
                    ClientCandidate.legal_name.ilike(pattern),
                    ClientCandidate.tax_id.ilike(pattern),
                    ClientCandidate.primary_email.ilike(pattern),
                    ClientCandidate.primary_phone.ilike(pattern),
                    ClientCandidate.street.ilike(pattern),
                    ClientCandidate.city.ilike(pattern),
                    source_label.c.source_label.ilike(pattern),
                ),
            )
            .order_by(ClientCandidate.updated_at.desc(), ClientCandidate.id.desc())
            .limit(limit)
            .all()
        )
        results = []
        for candidate, label in rows:
            reasons: list[str] = []
            score = 0.0
            if self._exact(q.folded, [candidate.name, candidate.legal_name]):
                reasons.append("name")
                score = 0.96
            elif self._contains(q.folded, [candidate.name, candidate.legal_name]):
                reasons.append("name")
                score = 0.84
            if self._exact(q.folded, [candidate.primary_email]):
                reasons.append("email")
                score = max(score, 0.96)
            elif self._contains(q.folded, [candidate.primary_email]):
                reasons.append("email")
                score = max(score, 0.88)
            if (
                q.phone_digits
                and self._local_phone_digits(candidate.primary_phone) == q.phone_digits
            ):
                reasons.append("phone")
                score = max(score, 0.96)
            if self._contains(q.folded, [candidate.tax_id]):
                reasons.append("nip")
                score = max(score, 0.9)
            if self._contains(q.folded, [candidate.street, candidate.city]):
                reasons.append("address")
                score = max(score, 0.78)
            if self._contains(q.folded, [label]):
                reasons.append("source")
                score = max(score, 0.74)
            results.append(
                self._result(
                    type="candidate",
                    id=candidate.id,
                    title=candidate.name,
                    subtitle=(
                        f"Kandydat · {candidate.status}"
                        + (f" · {label}" if label else "")
                    ),
                    snippet=self._matching_snippet(
                        q.folded,
                        [candidate.primary_email, candidate.primary_phone, candidate.city],
                    ),
                    score=score,
                    reasons=reasons,
                    occurred_at=candidate.updated_at,
                    client_id=candidate.matched_client_id,
                    route=f"/client-candidates/{candidate.id}",
                )
            )
        return results

    def _semantic_documents(self, q: _TextQuery, limit: int) -> list[GlobalSearchResult]:
        hits = self.semantic_service.search(
            query=q.value,
            limit=limit,
            create_collection_if_missing=False,
        )
        document_ids = list(dict.fromkeys(hit.document_id for hit in hits))
        if not document_ids:
            return []
        contexts = {
            row[0].id: row
            for row in (
                self.db.query(Document, Client.name, Project.name, Inspection.title)
                .outerjoin(Client, Client.id == Document.client_id)
                .outerjoin(Project, Project.id == Document.project_id)
                .outerjoin(Inspection, Inspection.id == Document.inspection_id)
                .filter(Document.id.in_(document_ids))
                .all()
            )
        }
        results = []
        for hit in hits:
            context = contexts.get(hit.document_id)
            if context is None:
                continue
            document, client_name, project_name, inspection_title = context
            del project_name, inspection_title
            results.append(
                self._result(
                    type="document",
                    id=document.id,
                    title=document.original_filename or document.filename,
                    subtitle=f"Klient: {client_name}" if client_name else None,
                    snippet=self._snippet(hit.content),
                    score=min(0.69, max(0.5, 0.5 + hit.score * 0.19)),
                    reasons=["semantic"],
                    occurred_at=document.captured_at or document.created_at,
                    client_id=document.client_id,
                    project_id=document.project_id,
                    inspection_id=document.inspection_id,
                    route=f"/documents?document_id={document.id}",
                )
            )
        return results

    @classmethod
    def _merge(
        cls, items: Iterable[GlobalSearchResult]
    ) -> list[GlobalSearchResult]:
        merged: dict[tuple[str, int], GlobalSearchResult] = {}
        for item in items:
            key = (item.type, item.id)
            current = merged.get(key)
            if current is None:
                merged[key] = item
                continue
            reasons = list(
                dict.fromkeys([*current.match_reasons, *item.match_reasons])
            )
            winner = item if item.score > current.score else current
            merged[key] = winner.model_copy(
                update={
                    "match_reasons": reasons,
                    "match_reason": reasons[0],
                    "snippet": winner.snippet or current.snippet or item.snippet,
                }
            )
        return list(merged.values())

    @classmethod
    def _sort_key(cls, item: GlobalSearchResult):
        timestamp = item.occurred_at.timestamp() if item.occurred_at else 0.0
        return (-item.score, cls._type_order[item.type], -timestamp, -item.id)

    @staticmethod
    def _result(
        *, reasons: list[str], score: float, **values
    ) -> GlobalSearchResult:
        unique = list(dict.fromkeys(reasons)) or ["text"]
        return GlobalSearchResult(
            **values,
            score=round(score or 0.6, 6),
            match_reason=unique[0],
            match_reasons=unique,
        )

    @staticmethod
    def _contains(query: str, values: Iterable[object | None]) -> bool:
        return any(
            query in str(value).casefold()
            for value in values
            if value is not None
        )

    @staticmethod
    def _exact(query: str, values: Iterable[object | None]) -> bool:
        return any(
            " ".join(str(value).split()).casefold() == query
            for value in values
            if value is not None
        )

    @staticmethod
    def _local_phone_digits(value: object | None) -> str:
        digits = re.sub(r"\D", "", str(value or ""))
        return digits[2:] if len(digits) == 11 and digits.startswith("48") else digits

    @staticmethod
    def _snippet(value: object | None) -> str | None:
        normalized = " ".join(str(value or "").split())
        if not normalized:
            return None
        if len(normalized) <= SNIPPET_LIMIT:
            return normalized
        return normalized[: SNIPPET_LIMIT - 1].rstrip() + "…"

    @classmethod
    def _matching_snippet(
        cls, query: str, values: Iterable[object | None]
    ) -> str | None:
        for value in values:
            if value is not None and query in str(value).casefold():
                return cls._snippet(value)
        return None

    @classmethod
    def _address(cls, values: Iterable[object | None]) -> str | None:
        return cls._snippet(
            " ".join(
                str(value).strip()
                for value in values
                if value and str(value).strip()
            )
        )

    @staticmethod
    def _is_semantic_query(q: _TextQuery) -> bool:
        letters = sum(character.isalpha() for character in q.value)
        return letters >= 3 and "@" not in q.value and not (
            q.digits and letters == 0
        )
