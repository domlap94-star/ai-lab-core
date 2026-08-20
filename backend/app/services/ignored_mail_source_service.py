from __future__ import annotations

from datetime import datetime, timezone
import re

from sqlalchemy.orm import Session

from app.models.ignored_mail_source import IgnoredMailSource
from app.services.change_history_service import ChangeHistoryService


EMAIL_RE = re.compile(r"^[^@\s]+@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.IGNORECASE)
DOMAIN_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.IGNORECASE)


class IgnoredMailSourceValidationError(ValueError):
    pass


class IgnoredMailSourceNotFoundError(LookupError):
    pass


def normalize_ignored_mail_value(rule_type: str, value: str) -> str:
    normalized = value.strip().lower()
    if rule_type == "email":
        if not EMAIL_RE.fullmatch(normalized):
            raise IgnoredMailSourceValidationError("invalid_ignored_email")
        return normalized
    if rule_type == "domain":
        normalized = normalized.lstrip("@")
        if any(part in normalized for part in ("://", "/", "?", "#", "*")) or not DOMAIN_RE.fullmatch(normalized):
            raise IgnoredMailSourceValidationError("invalid_ignored_domain")
        return normalized
    raise IgnoredMailSourceValidationError("invalid_ignored_rule_type")


class IgnoredMailSourceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, *, include_inactive: bool = False) -> list[IgnoredMailSource]:
        query = self.db.query(IgnoredMailSource)
        if not include_inactive:
            query = query.filter(IgnoredMailSource.is_active.is_(True))
        return query.order_by(IgnoredMailSource.rule_type, IgnoredMailSource.normalized_value).all()

    def ignore(self, *, rule_type: str, value: str, actor_user_id: int) -> IgnoredMailSource:
        normalized = normalize_ignored_mail_value(rule_type, value)
        rule = self.db.query(IgnoredMailSource).filter(
            IgnoredMailSource.rule_type == rule_type,
            IgnoredMailSource.normalized_value == normalized,
        ).with_for_update().first()
        now = datetime.now(timezone.utc)
        before: dict[str, object] = {}
        action = "created"
        if rule is None:
            rule = IgnoredMailSource(
                rule_type=rule_type,
                normalized_value=normalized,
                is_active=True,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
                updated_at=now,
            )
            self.db.add(rule)
            self.db.flush()
        else:
            before = self._history_snapshot(rule)
            if rule.is_active:
                return rule
            rule.is_active = True
            rule.updated_by_user_id = actor_user_id
            rule.updated_at = now
            self.db.flush()
            action = "activated"
        ChangeHistoryService(self.db).persist(
            actor_user_id=actor_user_id,
            entity_type="ignored_mail_source",
            entity_id=rule.id,
            action=action,
            before=before,
            after=self._history_snapshot(rule),
            source_key=f"ignored-mail:{rule.id}:{int(now.timestamp() * 1000000)}",
        )
        return rule

    def unignore(self, *, rule_id: int, actor_user_id: int) -> IgnoredMailSource:
        rule = self.db.query(IgnoredMailSource).filter(IgnoredMailSource.id == rule_id).with_for_update().first()
        if rule is None:
            raise IgnoredMailSourceNotFoundError("ignored_mail_source_not_found")
        if not rule.is_active:
            return rule
        before = self._history_snapshot(rule)
        now = datetime.now(timezone.utc)
        rule.is_active = False
        rule.updated_by_user_id = actor_user_id
        rule.updated_at = now
        self.db.flush()
        ChangeHistoryService(self.db).persist(
            actor_user_id=actor_user_id,
            entity_type="ignored_mail_source",
            entity_id=rule.id,
            action="deactivated",
            before=before,
            after=self._history_snapshot(rule),
            source_key=f"ignored-mail:{rule.id}:{int(now.timestamp() * 1000000)}",
        )
        return rule

    def matches(self, sender: str | None) -> bool:
        normalized = (sender or "").strip().lower()
        if not EMAIL_RE.fullmatch(normalized):
            return False
        domain = normalized.rsplit("@", 1)[1]
        return self.db.query(IgnoredMailSource.id).filter(
            IgnoredMailSource.is_active.is_(True),
            ((IgnoredMailSource.rule_type == "email") & (IgnoredMailSource.normalized_value == normalized))
            | ((IgnoredMailSource.rule_type == "domain") & (IgnoredMailSource.normalized_value == domain)),
        ).first() is not None

    @staticmethod
    def _history_snapshot(rule: IgnoredMailSource) -> dict[str, object]:
        return {
            "rule_type": rule.rule_type,
            "email" if rule.rule_type == "email" else "domain": rule.normalized_value,
            "is_active": rule.is_active,
        }
