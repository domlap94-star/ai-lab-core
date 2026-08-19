from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Query, Session

from app.models.candidate_merge_event import CandidateMergeEvent
from app.models.change_history_event import ChangeHistoryEvent
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.document_client_link_event import DocumentClientLinkEvent
from app.models.user import User
from app.models.user_lifecycle_event import UserLifecycleEvent
from app.schemas.change_history import ChangeHistoryPage, ChangeHistoryRead


class ChangeHistoryQueryService:
    """Bounded admin projection over generic and canonical domain audits."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_page(
        self,
        *,
        entity_type: str | None = None,
        entity_id: int | None = None,
        actor_user_id: int | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> ChangeHistoryPage:
        window = skip + limit
        items: list[ChangeHistoryRead] = []
        totals = 0

        generic_query = self._time_actor_filters(
            self.db.query(ChangeHistoryEvent),
            ChangeHistoryEvent,
            actor_user_id,
            date_from,
            date_to,
        )
        if entity_type is not None:
            generic_query = generic_query.filter(
                ChangeHistoryEvent.entity_type == entity_type
            )
        if entity_id is not None:
            generic_query = generic_query.filter(
                ChangeHistoryEvent.entity_id == entity_id
            )
        if action is not None:
            generic_query = generic_query.filter(ChangeHistoryEvent.action == action)
        totals += generic_query.count()
        generic_rows = (
            generic_query.order_by(
                ChangeHistoryEvent.created_at.desc(), ChangeHistoryEvent.id.desc()
            )
            .limit(window)
            .all()
        )
        items.extend(self._generic(row) for row in generic_rows)

        if self._source_allowed(entity_type, action, "candidate_merge", "merged"):
            query = self._time_actor_filters(
                self.db.query(CandidateMergeEvent),
                CandidateMergeEvent,
                actor_user_id,
                date_from,
                date_to,
            )
            if entity_id is not None:
                query = query.filter(CandidateMergeEvent.candidate_id == entity_id)
            totals += query.count()
            rows = query.order_by(
                CandidateMergeEvent.created_at.desc(),
                CandidateMergeEvent.id.desc(),
            ).limit(window).all()
            items.extend(self._candidate_merge(row) for row in rows)

        document_actions = {"LINK": "linked", "UNLINK": "unlinked", "MOVE": "moved"}
        if entity_type in (None, "document") and action in (
            None, *document_actions.values()
        ):
            query = self._time_actor_filters(
                self.db.query(DocumentClientLinkEvent),
                DocumentClientLinkEvent,
                actor_user_id,
                date_from,
                date_to,
            )
            if entity_id is not None:
                query = query.filter(DocumentClientLinkEvent.document_id == entity_id)
            if action is not None:
                db_action = next(
                    key for key, value in document_actions.items() if value == action
                )
                query = query.filter(DocumentClientLinkEvent.action == db_action)
            totals += query.count()
            rows = query.order_by(
                DocumentClientLinkEvent.created_at.desc(),
                DocumentClientLinkEvent.id.desc(),
            ).limit(window).all()
            items.extend(self._document_link(row, document_actions[row.action]) for row in rows)

        if self._source_allowed(entity_type, action, "user", "deactivated"):
            query = self._time_actor_filters(
                self.db.query(UserLifecycleEvent),
                UserLifecycleEvent,
                actor_user_id,
                date_from,
                date_to,
            )
            if entity_id is not None:
                query = query.filter(UserLifecycleEvent.target_user_id == entity_id)
            totals += query.count()
            rows = query.order_by(
                UserLifecycleEvent.created_at.desc(), UserLifecycleEvent.id.desc()
            ).limit(window).all()
            items.extend(self._user_lifecycle(row) for row in rows)

        actor_ids = {item.actor_user_id for item in items if item.actor_user_id}
        actors = {
            user.id: user.username
            for user in self.db.query(User).filter(User.id.in_(actor_ids)).all()
        } if actor_ids else {}
        client_ids = {
            item.entity_id
            for item in items
            if item.entity_type in {"client", "client_workflow_status"}
        }
        clients = {
            row.id: row.name
            for row in self.db.query(Client).filter(Client.id.in_(client_ids)).all()
        } if client_ids else {}
        candidate_ids = {
            item.entity_id
            for item in items
            if item.entity_type in {"client_candidate", "candidate_merge"}
        }
        candidates = {
            row.id: row.name
            for row in self.db.query(ClientCandidate)
            .filter(ClientCandidate.id.in_(candidate_ids)).all()
        } if candidate_ids else {}

        enriched: list[ChangeHistoryRead] = []
        for item in items:
            label = item.entity_label
            if item.entity_type in {"client", "client_workflow_status"}:
                label = clients.get(item.entity_id, f"Klient #{item.entity_id}")
            elif item.entity_type in {"client_candidate", "candidate_merge"}:
                label = candidates.get(item.entity_id, f"Kandydat #{item.entity_id}")
            enriched.append(
                item.model_copy(
                    update={
                        "actor_display_name": actors.get(item.actor_user_id),
                        "entity_label": label,
                    }
                )
            )

        enriched.sort(
            key=lambda item: (item.created_at, item.stable_key), reverse=True
        )
        return ChangeHistoryPage(
            items=enriched[skip:window],
            total=totals,
            skip=skip,
            limit=limit,
        )

    @staticmethod
    def _time_actor_filters(
        query: Query,
        model,
        actor_user_id: int | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> Query:
        if actor_user_id is not None:
            query = query.filter(model.actor_user_id == actor_user_id)
        if date_from is not None:
            query = query.filter(model.created_at >= date_from)
        if date_to is not None:
            query = query.filter(model.created_at <= date_to)
        return query

    @staticmethod
    def _source_allowed(
        requested_entity: str | None,
        requested_action: str | None,
        entity: str,
        action: str,
    ) -> bool:
        return requested_entity in (None, entity) and requested_action in (None, action)

    @staticmethod
    def _generic(row: ChangeHistoryEvent) -> ChangeHistoryRead:
        deep_link = None
        if row.entity_type in {"client", "client_workflow_status"}:
            deep_link = f"/clients/{row.entity_id}"
        elif row.entity_type in {"client_candidate", "candidate_merge"}:
            deep_link = f"/client-candidates/{row.entity_id}"
        return ChangeHistoryRead(
            stable_key=f"change:{row.id}",
            source_type="change_history",
            created_at=row.created_at,
            actor_user_id=row.actor_user_id,
            actor_display_name=None,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            entity_label=f"{row.entity_type} #{row.entity_id}",
            action=row.action,
            changed_fields=list(row.changed_fields),
            before_values=dict(row.before_values),
            after_values=dict(row.after_values),
            deep_link=deep_link,
        )

    @staticmethod
    def _candidate_merge(row: CandidateMergeEvent) -> ChangeHistoryRead:
        return ChangeHistoryRead(
            stable_key=f"candidate-merge:{row.id}",
            source_type="candidate_merge",
            created_at=row.created_at,
            actor_user_id=row.actor_user_id,
            actor_display_name=None,
            entity_type="candidate_merge",
            entity_id=row.candidate_id,
            entity_label=f"Kandydat #{row.candidate_id}",
            action="merged",
            changed_fields=list(row.changed_fields),
            before_values={},
            after_values={
                "target_client_id": row.target_client_id,
                "relation_counts": dict(row.relation_counts),
            },
            deep_link=f"/client-candidates/{row.candidate_id}",
        )

    @staticmethod
    def _document_link(
        row: DocumentClientLinkEvent, action: str
    ) -> ChangeHistoryRead:
        return ChangeHistoryRead(
            stable_key=f"document-link:{row.id}",
            source_type="document_client_link",
            created_at=row.created_at,
            actor_user_id=row.actor_user_id,
            actor_display_name=None,
            entity_type="document",
            entity_id=row.document_id,
            entity_label=f"Dokument #{row.document_id}",
            action=action,
            changed_fields=["client_id"],
            before_values={"client_id": row.old_client_id},
            after_values={"client_id": row.new_client_id},
            deep_link=f"/documents?document_id={row.document_id}",
        )

    @staticmethod
    def _user_lifecycle(row: UserLifecycleEvent) -> ChangeHistoryRead:
        return ChangeHistoryRead(
            stable_key=f"user-lifecycle:{row.id}",
            source_type="user_lifecycle",
            created_at=row.created_at,
            actor_user_id=row.actor_user_id,
            actor_display_name=None,
            entity_type="user",
            entity_id=row.target_user_id,
            entity_label=f"Użytkownik #{row.target_user_id}",
            action="deactivated",
            changed_fields=["is_active"],
            before_values={"is_active": True},
            after_values={"is_active": False},
            deep_link="/settings",
        )
