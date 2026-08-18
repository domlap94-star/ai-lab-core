from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.client_workflow_status import ClientWorkflowStatus
from app.models.document import Document
from app.models.inspection import Inspection
from app.models.project import Project
from app.repositories.client_email_repository import LINKED_CANDIDATE_STATUSES
from app.schemas.business_assistant import BusinessCoverage, BusinessSource


STATUS_LABELS = {
    "obsolete": "Nieaktualne", "in_progress": "W toku",
    "inspection": "Oględziny", "completed": "Zakończone",
    "untouched": "Nietknięte", "phone_contact": "Kontakt telefoniczny",
}


@dataclass(frozen=True)
class AnalyticsAnswer:
    answer: str
    sources: list[BusinessSource]
    coverage: BusinessCoverage


class BusinessAnalyticsService:
    """Deterministic, read-only company metrics; it never asks an LLM to count."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def direct_answer(self, question: str, now: datetime | None = None) -> AnalyticsAnswer | None:
        now = now or datetime.now(UTC)
        q = question.casefold()
        coverage = self.coverage()
        if "ilu" in q and "klient" in q and "aktywn" in q:
            count = self._active_clients().count()
            return self._answer(f"Mamy {count} aktywnych klientów.", "Aktywni klienci", count, coverage, now)
        if "ilu" in q and "klient" in q and "status" in q:
            status = next((key for key, label in STATUS_LABELS.items() if label.casefold() in q or key in q), None)
            if status:
                count = self._active_clients().join(
                    ClientWorkflowStatus, ClientWorkflowStatus.client_id == Client.id
                ).filter(ClientWorkflowStatus.deleted_at.is_(None), ClientWorkflowStatus.status == status).count()
                return self._answer(f"Status {STATUS_LABELS[status]} ma {count} klientów.", f"Klienci — {STATUS_LABELS[status]}", count, coverage, now)
        if "któr" in q and ("nieaktual" in q or "obsolete" in q):
            rows = self._active_clients().join(
                ClientWorkflowStatus, ClientWorkflowStatus.client_id == Client.id
            ).filter(ClientWorkflowStatus.deleted_at.is_(None), ClientWorkflowStatus.status == "obsolete").order_by(Client.name, Client.id).limit(20).all()
            sources = [self._entity("client", row.id, row.name, f"/clients/{row.id}", row.updated_at) for row in rows]
            text = ", ".join(row.name for row in rows) if rows else "brak"
            return AnalyticsAnswer(f"Nieaktualni klienci ({len(rows)}): {text}.", sources, coverage)
        if "ilu" in q and "klient" in q and ("tym miesią" in q or "tego miesią" in q):
            start = now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            count = self._active_clients().filter(Client.created_at >= start).count()
            return self._answer(f"W tym miesiącu dodano {count} klientów.", "Klienci dodani w tym miesiącu", count, coverage, now)
        if "ilu" in q and "kandyd" in q and any(word in q for word in ("oczek", "pending")):
            count = self.db.query(ClientCandidate).filter(ClientCandidate.deleted_at.is_(None), ClientCandidate.status == "pending").count()
            return self._answer(f"Oczekuje {count} kandydatów.", "Oczekujący kandydaci", count, coverage, now)
        if "kandyd" in q and any(word in q for word in ("duplik", "konflikt")):
            rows = self.db.query(ClientCandidate).filter(
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.status == "duplicate",
            ).order_by(ClientCandidate.updated_at.desc(), ClientCandidate.id.desc()).limit(20).all()
            sources = [self._entity("candidate", row.id, row.name, f"/client-candidates/{row.id}", row.updated_at) for row in rows]
            return AnalyticsAnswer(f"Znaleziono {len(rows)} kandydatów oznaczonych jako duplikat. Model nie przechowuje osobnego statusu konfliktu.", sources or [BusinessSource(source_type="analytics", title="Duplikaty kandydatów", date=now, snippet="Wynik: 0")], coverage)
        if "ile" in q and "dokument" in q and any(word in q for word in ("tygod", "7 dni")):
            since = now - timedelta(days=7)
            count = self.db.query(Document).filter(Document.created_at >= since).count()
            return self._answer(f"W ostatnich 7 dniach dodano {count} dokumentów.", "Dokumenty — ostatnie 7 dni", count, coverage, now)
        if "wizj" in q and any(word in q for word in ("zaplan", "w toku", "odby")):
            status = "planned" if "zaplan" in q else "in_progress" if "w toku" in q else "completed"
            rows = self.db.query(Inspection).filter(Inspection.deleted_at.is_(None), Inspection.status == status).order_by(Inspection.scheduled_at.desc().nulls_last(), Inspection.id.desc()).limit(20).all()
            sources = [self._entity("inspection", row.id, row.title, f"/inspections/{row.id}", row.scheduled_at or row.created_at) for row in rows]
            return AnalyticsAnswer(f"Znaleziono {len(rows)} wizji o statusie {status}.", sources, coverage)
        if "bez kontaktu" in q or "nie mieli kontaktu" in q:
            return self._stale_contacts(now, coverage)
        if any(word in q for word in ("najnowsze tematy", "najnowszych temat")) and any(word in q for word in ("mail", "e-mail")):
            return self._latest_email_topics(now, coverage)
        if "co wydarzy" in q or "ostatnich 7 dni" in q and "crm" in q:
            return self._recent_summary(now, coverage)
        if "pipeline" in q and any(word in q for word in ("podsum", "bieżą", "aktual")):
            return self._pipeline(coverage, now)
        if "aktywne realizac" in q or "aktywnych realizac" in q:
            rows = self.db.query(Project).filter(Project.deleted_at.is_(None), Project.status == "active").order_by(Project.updated_at.desc(), Project.id.desc()).limit(20).all()
            sources = [self._entity("project", row.id, row.name, f"/projects/{row.id}", row.updated_at) for row in rows]
            return AnalyticsAnswer(f"Aktywne realizacje: {len(rows)} (lista ograniczona do 20).", sources or [BusinessSource(source_type="analytics", title="Aktywne realizacje", date=now, snippet="Wynik: 0")], coverage)
        if "wymaga uwagi" in q or "wymagają uwagi" in q:
            return self._attention(now, coverage)
        return None

    def coverage(self) -> BusinessCoverage:
        return BusinessCoverage(
            clients_considered=self._active_clients().count(),
            candidates_considered=self.db.query(ClientCandidate).filter(ClientCandidate.deleted_at.is_(None)).count(),
            emails_searched=self.db.query(CandidateSource).filter(CandidateSource.deleted_at.is_(None), CandidateSource.source_type == "gmail_message").count(),
            documents_searched=self.db.query(Document).count(),
            inspections_considered=self.db.query(Inspection).filter(Inspection.deleted_at.is_(None)).count(),
            projects_considered=self.db.query(Project).filter(Project.deleted_at.is_(None)).count(),
        )

    def _active_clients(self):
        return self.db.query(Client).filter(Client.deleted_at.is_(None))

    def _stale_contacts(self, now: datetime, coverage: BusinessCoverage) -> AnalyticsAnswer:
        cutoff = now - timedelta(days=30)
        latest = self.db.query(
            ClientCandidate.matched_client_id.label("client_id"),
            func.max(CandidateSource.created_at).label("last_contact"),
        ).join(CandidateSource, CandidateSource.candidate_id == ClientCandidate.id).filter(
            CandidateSource.source_type == "gmail_message",
            CandidateSource.deleted_at.is_(None), ClientCandidate.deleted_at.is_(None),
            ClientCandidate.status.in_(LINKED_CANDIDATE_STATUSES),
            ClientCandidate.matched_client_id.isnot(None),
        ).group_by(ClientCandidate.matched_client_id).subquery()
        rows = self._active_clients().outerjoin(latest, latest.c.client_id == Client.id).filter(
            (latest.c.last_contact < cutoff) | latest.c.last_contact.is_(None)
        ).order_by(latest.c.last_contact.asc().nulls_first(), Client.id).limit(20).all()
        sources = [self._entity("client", row.id, row.name, f"/clients/{row.id}", row.updated_at) for row in rows]
        return AnalyticsAnswer(f"Znaleziono {len(rows)} klientów bez kontaktu e-mail w ostatnich 30 dniach (lista ograniczona do 20).", sources, coverage)

    def _latest_email_topics(self, now: datetime, coverage: BusinessCoverage) -> AnalyticsAnswer:
        rows = self.db.query(
            CandidateSource.id,
            CandidateSource.source_label,
            CandidateSource.created_at,
            ClientCandidate.matched_client_id,
        ).join(
            ClientCandidate, ClientCandidate.id == CandidateSource.candidate_id
        ).filter(
            CandidateSource.deleted_at.is_(None), CandidateSource.source_type == "gmail_message",
            ClientCandidate.deleted_at.is_(None), ClientCandidate.status.in_(LINKED_CANDIDATE_STATUSES),
            ClientCandidate.matched_client_id.isnot(None),
        ).order_by(CandidateSource.created_at.desc(), CandidateSource.id.desc()).limit(10).all()
        sources = [BusinessSource(source_type="email", source_id=row.id, title=(row.source_label or "Wiadomość e-mail")[:255], date=row.created_at, route=f"/clients/{row.matched_client_id}?email_source_id={row.id}", snippet=(row.source_label or "Wiadomość e-mail")[:600]) for row in rows]
        return AnalyticsAnswer(f"Najnowsze tematy e-maili ({len(sources)}): " + (", ".join(item.title for item in sources) if sources else "brak") + ".", sources or [BusinessSource(source_type="analytics", title="Najnowsze tematy e-maili", date=now, snippet="Brak wiadomości")], coverage)

    def _attention(self, now: datetime, coverage: BusinessCoverage) -> AnalyticsAnswer:
        pending = self.db.query(ClientCandidate).filter(ClientCandidate.deleted_at.is_(None), ClientCandidate.status == "pending").count()
        overdue = self.db.query(Inspection).filter(Inspection.deleted_at.is_(None), Inspection.status == "planned", Inspection.scheduled_at.isnot(None), Inspection.scheduled_at < now).count()
        missing_contact = self._active_clients().filter(Client.primary_email.is_(None), Client.primary_phone.is_(None)).count()
        text = f"Deterministyczne sygnały uwagi: oczekujący kandydaci {pending}, przeterminowane zaplanowane wizje {overdue}, klienci bez głównego e-maila i telefonu {missing_contact}."
        return AnalyticsAnswer(text, [BusinessSource(source_type="analytics", title="Sygnały wymagające uwagi", date=now, snippet=text)], coverage)

    def _recent_summary(self, now: datetime, coverage: BusinessCoverage) -> AnalyticsAnswer:
        since = now - timedelta(days=7)
        values = {
            "klientów": self._active_clients().filter(Client.created_at >= since).count(),
            "kandydatów": self.db.query(ClientCandidate).filter(ClientCandidate.deleted_at.is_(None), ClientCandidate.created_at >= since).count(),
            "dokumentów": self.db.query(Document).filter(Document.created_at >= since).count(),
            "e-maili": self.db.query(CandidateSource).filter(CandidateSource.deleted_at.is_(None), CandidateSource.source_type == "gmail_message", CandidateSource.created_at >= since).count(),
            "wizji": self.db.query(Inspection).filter(Inspection.deleted_at.is_(None), Inspection.created_at >= since).count(),
            "realizacji": self.db.query(Project).filter(Project.deleted_at.is_(None), Project.created_at >= since).count(),
        }
        text = ", ".join(f"{count} {label}" for label, count in values.items())
        return self._answer(f"W ostatnich 7 dniach odnotowano: {text}.", "Aktywność CRM — ostatnie 7 dni", sum(values.values()), coverage, now)

    def _pipeline(self, coverage: BusinessCoverage, now: datetime) -> AnalyticsAnswer:
        grouped = dict(self.db.query(ClientWorkflowStatus.status, func.count(ClientWorkflowStatus.id)).join(Client, Client.id == ClientWorkflowStatus.client_id).filter(Client.deleted_at.is_(None), ClientWorkflowStatus.deleted_at.is_(None)).group_by(ClientWorkflowStatus.status).all())
        untouched = coverage.clients_considered - sum(grouped.values()) + grouped.get("untouched", 0)
        grouped["untouched"] = untouched
        text = ", ".join(f"{STATUS_LABELS[key]}: {value}" for key, value in grouped.items())
        return self._answer(f"Bieżący pipeline klientów: {text}.", "Pipeline klientów", coverage.clients_considered, coverage, now)

    @staticmethod
    def _answer(answer: str, title: str, count: int, coverage: BusinessCoverage, now: datetime) -> AnalyticsAnswer:
        return AnalyticsAnswer(answer, [BusinessSource(source_type="analytics", title=title, date=now, snippet=f"Wynik: {count}; stan na {now.isoformat()}.")], coverage)

    @staticmethod
    def _entity(source_type: str, source_id: int, title: str, route: str, date: datetime | None) -> BusinessSource:
        return BusinessSource(source_type=source_type, source_id=source_id, title=title, date=date, route=route, snippet=title)
