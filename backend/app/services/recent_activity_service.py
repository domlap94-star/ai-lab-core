from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from sqlalchemy.orm import Session

from app.models.absence_request import AbsenceRequest
from app.models.candidate_merge_event import CandidateMergeEvent
from app.models.change_history_event import ChangeHistoryEvent
from app.models.client import Client
from app.models.client_activity_event import ClientActivityEvent
from app.models.document import Document
from app.models.document_client_link_event import DocumentClientLinkEvent
from app.models.inspection import Inspection
from app.models.mail_send_operation import MailSendOperation
from app.models.project import Project
from app.models.user import User
from app.models.user_lifecycle_event import UserLifecycleEvent
from app.models.work_item import WorkItem
from app.schemas.recent_activity import RecentActivityItem, RecentActivityPage


_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class _Projected:
    stable_key: str
    timestamp: datetime
    actor_user_id: int | None
    action: str
    entity_type: str
    entity_id: int
    summary: str
    deep_link: str | None
    client_id: int | None = None
    semantic_key: str | None = None


class RecentActivityService:
    """Read-only, bounded projection over canonical operational audit sources."""

    MAX_LIMIT = 50
    MAX_SKIP = 500
    SUMMARY_LIMIT = 200
    ADMIN_ONLY_ENTITIES = frozenset({"user", "ignored_mail_source"})

    def __init__(self, db: Session) -> None:
        self.db = db
        self.last_diagnostics: dict[str, int] = {}

    def get_page(self, *, viewer: User, skip: int = 0, limit: int = 8) -> RecentActivityPage:
        if not 0 <= skip <= self.MAX_SKIP:
            raise ValueError("Invalid activity offset")
        if not 1 <= limit <= self.MAX_LIMIT:
            raise ValueError("Invalid activity limit")

        branch_limit = skip + limit + 1
        is_admin = bool(viewer.role and viewer.role.name == "Administrator")
        sources: list[tuple[str, list[_Projected]]] = [
            ("client_activity", self._activity_rows(branch_limit)),
            ("change_history", self._history_rows(branch_limit, is_admin=is_admin)),
            ("candidate_merge", self._candidate_merge_rows(branch_limit)),
            ("document_link", self._document_link_rows(branch_limit)),
        ]
        if is_admin:
            sources.append(("user_lifecycle", self._user_lifecycle_rows(branch_limit)))
        sources.extend(
            (
                ("document", self._document_rows(branch_limit)),
                ("mail_send", self._mail_send_rows(branch_limit)),
                ("project", self._project_rows(branch_limit)),
                ("inspection", self._inspection_rows(branch_limit)),
            )
        )
        projected = [row for _, rows in sources for row in rows]

        before_visibility = len(projected)
        projected = self._filter_absence_visibility(projected, viewer, is_admin)

        deduplicated: list[_Projected] = []
        semantic_seen: set[str] = set()
        stable_seen: set[str] = set()
        for row in projected:
            if row.stable_key in stable_seen:
                continue
            if row.semantic_key and row.semantic_key in semantic_seen:
                continue
            stable_seen.add(row.stable_key)
            if row.semantic_key:
                semantic_seen.add(row.semantic_key)
            deduplicated.append(row)

        self.last_diagnostics = {
            **{f"source_{name}": len(rows) for name, rows in sources},
            "rows_considered": before_visibility,
            "unsafe_suppressed": before_visibility - len(projected),
            "duplicates_suppressed": len(projected) - len(deduplicated),
        }

        deduplicated.sort(
            key=lambda row: (row.timestamp, row.stable_key), reverse=True
        )

        window = deduplicated[skip : skip + limit + 1]
        actor_ids = {row.actor_user_id for row in window if row.actor_user_id is not None}
        actors = {
            row.id: row.username
            for row in self.db.query(User.id, User.username).filter(User.id.in_(actor_ids)).all()
        } if actor_ids else {}
        client_ids = {row.client_id for row in window if row.client_id is not None}
        clients = {
            row.id: row.name
            for row in self.db.query(Client.id, Client.name).filter(Client.id.in_(client_ids)).all()
        } if client_ids else {}

        items = [
            RecentActivityItem(
                stable_key=row.stable_key,
                timestamp=row.timestamp,
                actor_user_id=row.actor_user_id,
                actor_display=actors.get(row.actor_user_id, "System"),
                action=row.action,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                summary=self._safe_text(row.summary),
                deep_link=row.deep_link,
                client_id=row.client_id,
                client_name=clients.get(row.client_id),
            )
            for row in window[:limit]
        ]
        return RecentActivityPage(
            items=items,
            skip=skip,
            limit=limit,
            has_more=len(window) > limit,
        )

    def _activity_rows(self, limit: int) -> list[_Projected]:
        rows = (
            self.db.query(ClientActivityEvent)
            .order_by(ClientActivityEvent.occurred_at.desc(), ClientActivityEvent.id.desc())
            .limit(limit)
            .all()
        )
        summaries = {
            "call_initiated": "Rozpoczęto połączenie z klientem",
            "client_status_changed": "Zmieniono status klienta",
            "email_received": "Odebrano wiadomość klienta",
            "email_sent": "Wysłano wiadomość do klienta",
            "document_added": "Dodano dokument klienta",
            "inspection_created": "Utworzono inspekcję",
            "candidate_merged": "Scalono kandydata z klientem",
            "task_created": "Dodano zadanie klienta",
            "task_completed": "Ukończono zadanie klienta",
            "realization_created": "Utworzono realizację klienta",
            "note_added": "Dodano notatkę klienta",
        }
        actions = {
            "call_initiated": "created",
            "client_status_changed": "status_changed",
            "email_received": "created",
            "email_sent": "created",
            "document_added": "created",
            "inspection_created": "created",
            "candidate_merged": "merged",
            "task_created": "created",
            "task_completed": "status_changed",
            "realization_created": "created",
            "note_added": "created",
        }
        result: list[_Projected] = []
        for row in rows:
            entity_type = row.entity_type or "client"
            entity_id = int(row.entity_id or row.client_id)
            action = actions.get(row.event_type, "updated")
            result.append(
                _Projected(
                    stable_key=f"activity:{row.id}",
                    timestamp=row.occurred_at,
                    actor_user_id=row.actor_user_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    summary=summaries.get(row.event_type, "Zarejestrowano aktywność klienta"),
                    deep_link=self._deep_link(entity_type, entity_id, row.client_id),
                    client_id=row.client_id,
                    semantic_key=self._semantic(entity_type, entity_id, action),
                )
            )
        return result

    def _history_rows(self, limit: int, *, is_admin: bool) -> list[_Projected]:
        query = self.db.query(ChangeHistoryEvent)
        if not is_admin:
            query = query.filter(~ChangeHistoryEvent.entity_type.in_(self.ADMIN_ONLY_ENTITIES))
        rows = query.order_by(ChangeHistoryEvent.created_at.desc(), ChangeHistoryEvent.id.desc()).limit(limit).all()

        work_item_ids = {
            row.entity_id for row in rows if row.entity_type == "work_item"
        }
        nested_work_ids = {
            int(value)
            for row in rows
            if row.entity_type in {"work_item_note", "work_item_document"}
            for value in [row.after_values.get("work_item_id") or row.before_values.get("work_item_id")]
            if isinstance(value, int)
        }
        work_items = {
            row.id: row
            for row in self.db.query(WorkItem).filter(WorkItem.id.in_(work_item_ids | nested_work_ids)).all()
        } if work_item_ids or nested_work_ids else {}

        result: list[_Projected] = []
        for row in rows:
            work_item_id = None
            client_id = None
            if row.entity_type == "work_item":
                work_item_id = row.entity_id
            elif row.entity_type in {"work_item_note", "work_item_document"}:
                candidate = row.after_values.get("work_item_id") or row.before_values.get("work_item_id")
                work_item_id = int(candidate) if isinstance(candidate, int) else None
            if work_item_id and work_item_id in work_items:
                client_id = work_items[work_item_id].client_id
            result.append(
                _Projected(
                    stable_key=f"change:{row.id}",
                    timestamp=row.created_at,
                    actor_user_id=row.actor_user_id,
                    action=row.action,
                    entity_type=row.entity_type,
                    entity_id=row.entity_id,
                    summary=self._history_summary(row, work_items.get(work_item_id) if work_item_id else None),
                    deep_link=self._history_deep_link(row, work_item_id),
                    client_id=client_id,
                    semantic_key=self._history_semantic(row),
                )
            )
        return result

    def _candidate_merge_rows(self, limit: int) -> list[_Projected]:
        rows = self.db.query(CandidateMergeEvent).order_by(CandidateMergeEvent.created_at.desc(), CandidateMergeEvent.id.desc()).limit(limit).all()
        return [
            _Projected(
                stable_key=f"candidate-merge:{row.id}", timestamp=row.created_at,
                actor_user_id=row.actor_user_id, action="merged", entity_type="candidate_merge",
                entity_id=row.candidate_id, summary="Scalono kandydata z klientem",
                deep_link=f"/client-candidates/{row.candidate_id}", client_id=row.target_client_id,
                semantic_key=self._semantic("candidate_merge", row.candidate_id, "merged"),
            ) for row in rows
        ]

    def _document_link_rows(self, limit: int) -> list[_Projected]:
        rows = self.db.query(DocumentClientLinkEvent).order_by(DocumentClientLinkEvent.created_at.desc(), DocumentClientLinkEvent.id.desc()).limit(limit).all()
        actions = {"LINK": "linked", "UNLINK": "unlinked", "MOVE": "moved"}
        summaries = {"LINK": "Powiązano dokument z klientem", "UNLINK": "Usunięto powiązanie dokumentu z klientem", "MOVE": "Przeniesiono dokument do innego klienta"}
        return [
            _Projected(
                stable_key=f"document-link:{row.id}", timestamp=row.created_at,
                actor_user_id=row.actor_user_id, action=actions[row.action], entity_type="document",
                entity_id=row.document_id, summary=summaries[row.action],
                deep_link=f"/documents?document_id={row.document_id}",
                client_id=row.new_client_id or row.old_client_id,
                semantic_key=self._semantic("document", row.document_id, actions[row.action]),
            ) for row in rows
        ]

    def _user_lifecycle_rows(self, limit: int) -> list[_Projected]:
        rows = self.db.query(UserLifecycleEvent).order_by(UserLifecycleEvent.created_at.desc(), UserLifecycleEvent.id.desc()).limit(limit).all()
        return [
            _Projected(
                stable_key=f"user-lifecycle:{row.id}", timestamp=row.created_at,
                actor_user_id=row.actor_user_id, action=row.action.lower(), entity_type="user",
                entity_id=row.target_user_id, summary="Zmieniono stan użytkownika",
                deep_link="/settings", semantic_key=self._semantic("user", row.target_user_id, row.action.lower()),
            ) for row in rows
        ]

    def _document_rows(self, limit: int) -> list[_Projected]:
        rows = self.db.query(Document).filter(
            Document.trashed_at.is_(None),
            Document.purged_at.is_(None),
        ).order_by(Document.created_at.desc(), Document.id.desc()).limit(limit).all()
        return [
            _Projected(
                stable_key=f"document-created:{row.id}", timestamp=row.created_at,
                actor_user_id=None, action="created", entity_type="document", entity_id=row.id,
                summary=f"Dodano dokument „{self._safe_text(row.original_filename or row.filename, 100)}”",
                deep_link=f"/documents?document_id={row.id}", client_id=row.client_id,
                semantic_key=self._semantic("document", row.id, "created"),
            ) for row in rows
        ]

    def _mail_send_rows(self, limit: int) -> list[_Projected]:
        rows = self.db.query(MailSendOperation).filter(MailSendOperation.status == "canonical_synced").order_by(MailSendOperation.updated_at.desc(), MailSendOperation.id.desc()).limit(limit).all()
        labels = {"compose": "Wysłano nową wiadomość", "reply": "Wysłano odpowiedź", "forward": "Przekazano wiadomość"}
        return [
            _Projected(
                stable_key=f"mail-send:{row.id}", timestamp=row.updated_at,
                actor_user_id=row.actor_user_id, action=row.action, entity_type="mail",
                entity_id=int(row.canonical_source_id or row.id), summary=labels.get(row.action, "Wysłano wiadomość"),
                deep_link="/mail", client_id=row.client_id,
                semantic_key=self._semantic("mail", int(row.canonical_source_id or row.id), row.action),
            ) for row in rows
        ]

    def _project_rows(self, limit: int) -> list[_Projected]:
        rows = self.db.query(Project).order_by(Project.created_at.desc(), Project.id.desc()).limit(limit).all()
        return [
            _Projected(
                stable_key=f"project-created:{row.id}", timestamp=row.created_at,
                actor_user_id=row.created_by_user_id, action="created", entity_type="project",
                entity_id=row.id, summary=f"Utworzono projekt „{self._safe_text(row.name, 100)}”",
                deep_link=f"/projects/{row.id}", client_id=row.client_id,
                semantic_key=self._semantic("project", row.id, "created"),
            ) for row in rows
        ]

    def _inspection_rows(self, limit: int) -> list[_Projected]:
        rows = self.db.query(Inspection).order_by(Inspection.created_at.desc(), Inspection.id.desc()).limit(limit).all()
        return [
            _Projected(
                stable_key=f"inspection-created:{row.id}", timestamp=row.created_at,
                actor_user_id=row.created_by_user_id, action="created", entity_type="inspection",
                entity_id=row.id, summary=f"Utworzono inspekcję „{self._safe_text(row.title, 100)}”",
                deep_link=f"/inspections/{row.id}", client_id=row.client_id,
                semantic_key=self._semantic("inspection", row.id, "created"),
            ) for row in rows
        ]

    def _filter_absence_visibility(self, rows: list[_Projected], viewer: User, is_admin: bool) -> list[_Projected]:
        if is_admin:
            return rows
        absence_ids = {row.entity_id for row in rows if row.entity_type == "absence_request"}
        own_ids = {
            row.id for row in self.db.query(AbsenceRequest.id).filter(
                AbsenceRequest.id.in_(absence_ids), AbsenceRequest.requester_user_id == viewer.id
            ).all()
        } if absence_ids else set()
        return [row for row in rows if row.entity_type != "absence_request" or row.entity_id in own_ids]

    def _history_summary(self, row: ChangeHistoryEvent, work_item: WorkItem | None) -> str:
        action_labels = {
            "created": "Utworzono", "updated": "Zaktualizowano", "deleted": "Zarchiwizowano",
            "restored": "Przywrócono", "status_changed": "Zmieniono status",
            "accepted": "Zaakceptowano", "rejected": "Odrzucono", "merged": "Scalono",
            "activated": "Aktywowano", "deactivated": "Dezaktywowano",
            "trashed": "Przeniesiono do kosza", "purged": "Usunięto trwale",
        }
        entities = {
            "client": "klienta", "client_contact": "kontakt klienta", "client_address": "adres klienta",
            "client_workflow_status": "status klienta", "client_candidate": "kandydata",
            "candidate_merge": "kandydata", "ignored_mail_source": "regułę ignorowania nadawcy",
            "user": "użytkownika", "work_item": "zadanie", "work_item_note": "notatkę do zadania",
            "work_item_document": "załącznik zadania", "absence_request": "wniosek o absencję",
            "document": "dokument",
        }
        base = f"{action_labels.get(row.action, 'Zmieniono')} {entities.get(row.entity_type, 'element')}"
        if row.entity_type == "work_item" and work_item is not None:
            return f"{base} „{self._safe_text(work_item.title, 100)}”"
        return base

    @classmethod
    def _history_semantic(cls, row: ChangeHistoryEvent) -> str:
        # Workflow status history uses the Client ID as entity_id. Normalize it
        # to the explicit client Activity identity so one status change appears once.
        entity_type = "client" if row.entity_type == "client_workflow_status" else row.entity_type
        return cls._semantic(entity_type, row.entity_id, row.action)

    @staticmethod
    def _history_deep_link(row: ChangeHistoryEvent, work_item_id: int | None) -> str | None:
        if row.entity_type in {"client", "client_workflow_status"}:
            return f"/clients/{row.entity_id}"
        if row.entity_type in {"client_candidate", "candidate_merge"}:
            return f"/client-candidates/{row.entity_id}"
        if row.entity_type == "work_item":
            return f"/tasks/{row.entity_id}"
        if row.entity_type in {"work_item_note", "work_item_document"} and work_item_id:
            return f"/tasks/{work_item_id}"
        if row.entity_type == "absence_request":
            return f"/tasks?absence_id={row.entity_id}"
        if row.entity_type in {"user", "ignored_mail_source"}:
            return "/settings"
        return None

    @staticmethod
    def _deep_link(entity_type: str, entity_id: int, client_id: int | None) -> str | None:
        if entity_type in {"client", "client_contact_point"} or client_id:
            return f"/clients/{client_id or entity_id}"
        if entity_type == "document":
            return f"/documents?document_id={entity_id}"
        if entity_type == "inspection":
            return f"/inspections/{entity_id}"
        if entity_type in {"work_item", "task", "realization"}:
            return f"/tasks/{entity_id}"
        return None

    @staticmethod
    def _semantic(entity_type: str, entity_id: int, action: str) -> str:
        return f"{entity_type}:{entity_id}:{action}"

    @classmethod
    def _safe_text(cls, value: str, limit: int | None = None) -> str:
        text = _WHITESPACE.sub(" ", value).strip()
        maximum = limit or cls.SUMMARY_LIMIT
        return text if len(text) <= maximum else text[: maximum - 1].rstrip() + "…"
