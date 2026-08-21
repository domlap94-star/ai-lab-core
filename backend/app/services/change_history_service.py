from __future__ import annotations

from datetime import date, datetime
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.change_history_event import ChangeHistoryEvent


class ChangeHistoryValidationError(ValueError):
    pass


class ChangeHistoryConflictError(ValueError):
    pass


class ChangeHistoryService:
    MAX_CHANGED_FIELDS = 40
    MAX_PAYLOAD_BYTES = 8 * 1024
    MAX_SCALAR_LENGTH = 255

    ENTITY_FIELDS = {
        "client": {
            "client_type", "name", "legal_name", "tax_id",
            "registration_number", "industry_id", "website",
            "primary_email", "primary_phone", "street",
            "building_number", "unit_number", "postal_code", "city",
            "country_code", "notes", "client_added_at", "deleted_at", "purged_at",
        },
        "client_contact": {
            "client_id", "kind", "email", "phone", "is_primary",
            "position", "deleted_at",
        },
        "client_address": {
            "client_id", "label", "street", "building_number",
            "unit_number", "postal_code", "city", "country_code",
            "is_primary", "position", "deleted_at",
        },
        "client_workflow_status": {"status", "effective_date"},
        "client_candidate": {"status", "matched_client_id", "resulting_client_id"},
        "candidate_merge": {"target_client_id"},
        "ignored_mail_source": {"rule_type", "email", "domain", "is_active"},
        "user": {"username", "email", "role", "is_active", "trashed_at", "purged_at", "auth_version"},
        "document": {
            "trashed_at", "purged_at", "vector_points_deleted_count",
            "vector_collection", "purge_result",
        },
        "work_item": {
            "item_type", "title", "description", "start_at", "due_at",
            "all_day", "timezone_name", "status", "priority",
            "assignee_user_id", "client_id", "project_id", "party_name", "deleted_at",
            "completed_at", "version",
        },
        "work_item_note": {"work_item_id", "text", "deleted_at", "version"},
        "work_item_document": {"work_item_id", "note_id", "document_id", "detached_at"},
        "absence_request": {
            "requester_user_id", "absence_type", "start_date", "end_date",
            "status", "note", "reviewed_by_user_id", "reviewed_at",
            "review_note", "cancelled_by_user_id", "cancelled_at", "version",
        },
        "knowledge_base_item": {
            "title", "source", "publisher", "version", "effective_date",
            "category", "tags", "status", "supersedes_id",
            "processing_status", "processing_method", "analysis_status",
            "indexing_status", "archived_at",
        },
    }
    ACTIONS = {
        "created", "updated", "deleted", "restored", "status_changed",
        "accepted", "rejected", "merged", "activated", "deactivated",
        "trashed", "purged", "processing_retried",
    }
    SECRET_FIELD_PATTERN = re.compile(
        r"password|passwd|secret|token|cookie|authorization|api[_-]?key|"
        r"private[_-]?key|oauth|credential|environment|env[_-]?value|sql|"
        r"stack[_-]?trace|raw[_-]?payload|email[_-]?body|document[_-]?text|"
        r"ocr|vision|extracted[_-]?text",
        re.IGNORECASE,
    )

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def client_snapshot(client, *, include_nulls: bool = True) -> dict[str, Any]:
        fields = (
            "client_type", "name", "legal_name", "tax_id",
            "registration_number", "industry_id", "website",
            "primary_email", "primary_phone", "street", "building_number",
            "unit_number", "postal_code", "city", "country_code", "notes",
            "client_added_at", "deleted_at",
        )
        values = {field: getattr(client, field) for field in fields}
        return values if include_nulls else {
            field: value for field, value in values.items() if value is not None
        }

    @staticmethod
    def contact_snapshot(contact) -> dict[str, Any]:
        result: dict[str, Any] = {
            "client_id": contact.client_id,
            "kind": contact.kind,
            "is_primary": contact.is_primary,
            "position": contact.position,
            "deleted_at": contact.deleted_at,
        }
        result["email" if contact.kind == "email" else "phone"] = contact.value
        return result

    @staticmethod
    def address_snapshot(address) -> dict[str, Any]:
        return {
            field: getattr(address, field)
            for field in (
                "client_id", "label", "street", "building_number",
                "unit_number", "postal_code", "city", "country_code",
                "is_primary", "position", "deleted_at",
            )
        }

    @staticmethod
    def candidate_snapshot(candidate) -> dict[str, Any]:
        return {
            "status": candidate.status,
            "matched_client_id": candidate.matched_client_id,
        }

    def persist(
        self,
        *,
        actor_user_id: int | None,
        entity_type: str,
        entity_id: int,
        action: str,
        before: dict[str, Any],
        after: dict[str, Any],
        source_key: str,
        operation_id: str | None = None,
    ) -> ChangeHistoryEvent | None:
        if entity_type not in self.ENTITY_FIELDS:
            raise ChangeHistoryValidationError("Unsupported history entity type")
        if action not in self.ACTIONS:
            raise ChangeHistoryValidationError("Unsupported history action")
        if entity_id <= 0:
            raise ChangeHistoryValidationError("History entity ID must be positive")
        if not source_key or len(source_key) > 200 or self._contains_content(source_key):
            raise ChangeHistoryValidationError("Invalid history source key")
        if operation_id is not None and (not operation_id or len(operation_id) > 64):
            raise ChangeHistoryValidationError("Invalid history operation ID")

        allowed = self.ENTITY_FIELDS[entity_type]
        supplied = set(before) | set(after)
        unknown = supplied - allowed
        if unknown:
            raise ChangeHistoryValidationError(
                "Unsupported history fields: " + ", ".join(sorted(unknown))
            )
        suspicious = [field for field in supplied if self.SECRET_FIELD_PATTERN.search(field)]
        if suspicious:
            raise ChangeHistoryValidationError("Sensitive history field rejected")

        raw_changed = {
            field
            for field in supplied
            if before.get(field, _MISSING) != after.get(field, _MISSING)
        }
        if not raw_changed:
            return None
        clean_before = {
            field: self._sanitize(entity_type, field, before[field], before)
            for field in raw_changed
            if field in before
        }
        clean_after = {
            field: self._sanitize(entity_type, field, after[field], after)
            for field in raw_changed
            if field in after
        }
        changed = sorted(
            field
            for field in supplied
            if clean_before.get(field, _MISSING) != clean_after.get(field, _MISSING)
        )
        if not changed:
            return None
        if len(changed) > self.MAX_CHANGED_FIELDS:
            raise ChangeHistoryValidationError("Too many changed history fields")

        clean_before = {field: clean_before[field] for field in changed if field in clean_before}
        clean_after = {field: clean_after[field] for field in changed if field in clean_after}
        self._validate_payload_size(clean_before)
        self._validate_payload_size(clean_after)

        existing = (
            self.db.query(ChangeHistoryEvent)
            .filter(ChangeHistoryEvent.source_key == source_key)
            .first()
        )
        if existing is not None:
            expected = (
                actor_user_id,
                entity_type,
                entity_id,
                action,
                changed,
                clean_before,
                clean_after,
                operation_id,
            )
            actual = (
                existing.actor_user_id,
                existing.entity_type,
                existing.entity_id,
                existing.action,
                list(existing.changed_fields),
                dict(existing.before_values),
                dict(existing.after_values),
                existing.operation_id,
            )
            if actual != expected:
                raise ChangeHistoryConflictError(
                    "History source key belongs to another change"
                )
            return existing

        event = ChangeHistoryEvent(
            actor_user_id=actor_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            changed_fields=changed,
            before_values=clean_before,
            after_values=clean_after,
            operation_id=operation_id,
            source_key=source_key,
        )
        self.db.add(event)
        self.db.flush()
        return event

    @classmethod
    def _sanitize(
        cls,
        entity_type: str,
        field: str,
        value: Any,
        snapshot: dict[str, Any],
    ) -> Any:
        if value is None or isinstance(value, bool) or isinstance(value, int):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ChangeHistoryValidationError("Non-finite history value")
            return value
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Enum):
            value = value.value
        if not isinstance(value, str):
            raise ChangeHistoryValidationError("Nested or arbitrary history value rejected")

        normalized = " ".join(value.split())
        if field in {"tax_id", "registration_number"}:
            return cls._identifier_descriptor(normalized)
        if field == "primary_email" or field == "email":
            return cls._email_descriptor(normalized)
        if field == "primary_phone" or field == "phone":
            return cls._phone_descriptor(normalized)
        if field in {"notes", "description", "text", "note", "review_note"}:
            return cls._text_descriptor(value)
        if entity_type == "client_contact" and field == "kind":
            if normalized not in {"email", "phone"}:
                raise ChangeHistoryValidationError("Invalid contact kind")
        if len(normalized) > cls.MAX_SCALAR_LENGTH:
            raise ChangeHistoryValidationError("Oversized history scalar")
        return normalized

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @classmethod
    def _identifier_descriptor(cls, value: str) -> dict[str, str]:
        normalized = re.sub(r"\W", "", value).casefold()
        suffix = normalized[-4:]
        return {"masked": f"***{suffix}", "sha256": cls._digest(normalized)}

    @classmethod
    def _email_descriptor(cls, value: str) -> dict[str, str]:
        normalized = value.strip().casefold()
        local, separator, domain = normalized.partition("@")
        masked = f"{local[:1] or '*'}***@{domain}" if separator else "***"
        return {"masked": masked, "sha256": cls._digest(normalized)}

    @classmethod
    def _phone_descriptor(cls, value: str) -> dict[str, str]:
        normalized = re.sub(r"\D", "", value)
        return {
            "masked": f"***{normalized[-4:]}",
            "sha256": cls._digest(normalized),
        }

    @classmethod
    def _text_descriptor(cls, value: str) -> dict[str, int | str]:
        return {"length": len(value), "sha256": cls._digest(value)}

    @classmethod
    def _validate_payload_size(cls, value: dict[str, Any]) -> None:
        try:
            encoded = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise ChangeHistoryValidationError("History payload is not strict JSON") from error
        if len(encoded) > cls.MAX_PAYLOAD_BYTES:
            raise ChangeHistoryValidationError("History payload exceeds 8 KiB")

    @staticmethod
    def _contains_content(value: str) -> bool:
        lowered = value.casefold()
        return any(token in lowered for token in ("@", "bearer ", "select ", "\n", "\r"))


_MISSING = object()
