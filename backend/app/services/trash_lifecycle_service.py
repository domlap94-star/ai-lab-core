from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import secrets
import shutil

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.database.session import SessionLocal
from app.models.client import Client
from app.models.client_address import ClientAddress
from app.models.client_contact_point import ClientContactPoint
from app.models.document import Document
from app.models.document_asset import DocumentAsset
from app.models.document_chunk import DocumentChunk
from app.models.document_page import DocumentPage
from app.models.role import Role
from app.models.trash_entry import TrashEntry
from app.models.user import User
from app.services.change_history_service import ChangeHistoryService
from app.services.document_service import (
    DocumentContentUnavailableError,
    UnsafeDocumentStoragePathError,
    resolve_document_storage_path,
)
from app.services.qdrant_vector_store import (
    DocumentVectorReference,
    QdrantDocumentPurgeError,
    QdrantVectorStore,
)
from app.services.user_lifecycle_service import USER_LIFECYCLE_ADVISORY_LOCK_KEY, UserLifecycleService


TRASH_RETENTION = timedelta(days=7)
TRASH_PURGE_ADVISORY_LOCK_KEY = 6_202_608_201
ACTIVE_STATES = ("trashed", "purging", "blocked")


class TrashNotFoundError(Exception):
    pass


class TrashConflictError(Exception):
    pass


class TrashAuthorizationError(Exception):
    pass


class TrashPurgeBlockedError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class _MovedFile:
    source: Path
    quarantine: Path


class TrashLifecycleService:
    def __init__(
        self,
        db: Session,
        *,
        data_root: Path | None = None,
        vector_store: QdrantVectorStore | None = None,
    ) -> None:
        self.db = db
        self.data_root = (data_root or Path(settings.data_dir)).resolve()
        self.vector_store = vector_store or QdrantVectorStore()
        self.history = ChangeHistoryService(db)

    def _now(self) -> datetime:
        # The database clock is authoritative for the retention deadline and
        # keeps API and scheduled-runner decisions on the same time source.
        return self.db.execute(text("SELECT transaction_timestamp()")).scalar_one()

    def list_entries(self, *, entity_type: str | None, state: str | None, skip: int, limit: int):
        query = self.db.query(TrashEntry)
        if entity_type:
            query = query.filter(TrashEntry.entity_type == entity_type)
        if state:
            query = query.filter(TrashEntry.state == state)
        else:
            query = query.filter(TrashEntry.state.in_(("trashed", "purging", "blocked")))
        total = query.order_by(None).count()
        items = query.order_by(TrashEntry.trashed_at.desc(), TrashEntry.id.desc()).offset(skip).limit(limit).all()
        return items, total

    def trash(self, *, entity_type: str, entity_id: int, actor: User) -> TrashEntry:
        if actor.role.name != "Administrator":
            raise TrashAuthorizationError("Administrator role required")
        existing = self.db.query(TrashEntry).filter(
            TrashEntry.entity_type == entity_type,
            TrashEntry.entity_id == entity_id,
            TrashEntry.state.in_(ACTIVE_STATES),
        ).with_for_update().first()
        if existing:
            raise TrashConflictError("entity_already_trashed")
        now = self._now()
        if entity_type == "document":
            entity = self.db.query(Document).filter(Document.id == entity_id).with_for_update().first()
            if entity is None or entity.trashed_at is not None or entity.purged_at is not None:
                raise TrashNotFoundError("document_not_found")
            entity.trashed_at = now
            label = f"Dokument #{entity.id}"
            history_type = "document"
            before = {"trashed_at": None}
            after = {"trashed_at": now}
        elif entity_type == "client":
            entity = self.db.query(Client).filter(Client.id == entity_id, Client.deleted_at.is_(None)).with_for_update().first()
            if entity is None or entity.purged_at is not None:
                raise TrashNotFoundError("client_not_found")
            entity.deleted_at = now
            label = f"Klient #{entity.id}"
            history_type = "client"
            before = {"deleted_at": None}
            after = {"deleted_at": now}
        elif entity_type == "user":
            self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": USER_LIFECYCLE_ADVISORY_LOCK_KEY})
            entity = self.db.query(User).filter(User.id == entity_id).with_for_update().first()
            if entity is None or entity.trashed_at is not None or entity.purged_at is not None:
                raise TrashNotFoundError("user_not_found")
            if entity.id == actor.id:
                raise TrashConflictError("self_trash_forbidden")
            if entity.role.name == "Administrator" and entity.is_active:
                admins = self.db.query(User).join(Role).filter(User.is_active.is_(True), User.trashed_at.is_(None), Role.name == "Administrator").with_for_update().all()
                UserLifecycleService.ensure_admin_survives(target_user_id=entity.id, active_administrator_ids={item.id for item in admins})
            before = {"is_active": entity.is_active, "trashed_at": None, "auth_version": entity.auth_version}
            entity.is_active = False
            entity.trashed_at = now
            entity.auth_version += 1
            after = {"is_active": False, "trashed_at": now, "auth_version": entity.auth_version}
            label = f"Użytkownik #{entity.id}"
            history_type = "user"
        else:
            raise TrashConflictError("unsupported_entity_type")
        entry = TrashEntry(
            entity_type=entity_type,
            entity_id=entity_id,
            state="trashed",
            safe_display_label=label,
            trashed_at=now,
            purge_after=now + TRASH_RETENTION,
            trashed_by_user_id=actor.id,
        )
        self.db.add(entity)
        self.db.add(entry)
        self.db.flush()
        self.history.persist(
            actor_user_id=actor.id, entity_type=history_type, entity_id=entity_id,
            action="trashed", before=before, after=after,
            source_key=f"trash:{entry.id}:trashed",
        )
        return entry

    def restore(self, *, entry_id: int, actor: User) -> TrashEntry:
        if actor.role.name != "Administrator":
            raise TrashAuthorizationError("Administrator role required")
        entry = self.db.query(TrashEntry).filter(TrashEntry.id == entry_id).with_for_update().first()
        if entry is None:
            raise TrashNotFoundError("trash_entry_not_found")
        if entry.state == "purged":
            raise TrashConflictError("trash_entry_already_purged")
        if entry.state not in ("trashed", "blocked"):
            raise TrashConflictError("trash_entry_not_restorable")
        now = self._now()
        if now >= entry.purge_after:
            raise TrashConflictError("trash_retention_expired")
        if entry.entity_type == "document":
            entity = self.db.query(Document).filter(Document.id == entry.entity_id).with_for_update().first()
            if entity is None or entity.purged_at is not None:
                raise TrashConflictError("trash_entity_missing")
            try:
                path = resolve_document_storage_path(
                    storage_path=entity.storage_path or "",
                    data_root=self.data_root,
                )
            except (DocumentContentUnavailableError, UnsafeDocumentStoragePathError) as error:
                raise TrashConflictError("document_storage_unavailable") from error
            if entity.checksum_sha256 and self._sha256(path) != entity.checksum_sha256.lower():
                raise TrashConflictError("document_checksum_mismatch")
            before = {"trashed_at": entity.trashed_at}
            entity.trashed_at = None
            after = {"trashed_at": None}
            history_type = "document"
        elif entry.entity_type == "client":
            entity = self.db.query(Client).filter(Client.id == entry.entity_id).with_for_update().first()
            if entity is None or entity.purged_at is not None:
                raise TrashConflictError("trash_entity_missing")
            before = {"deleted_at": entity.deleted_at}
            entity.deleted_at = None
            after = {"deleted_at": None}
            history_type = "client"
        else:
            self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": USER_LIFECYCLE_ADVISORY_LOCK_KEY})
            entity = self.db.query(User).filter(User.id == entry.entity_id).with_for_update().first()
            if entity is None or entity.purged_at is not None:
                raise TrashConflictError("trash_entity_missing")
            duplicate = self.db.query(User).filter(User.id != entity.id, (func.lower(User.username) == entity.username.lower()) | (func.lower(User.email) == entity.email.lower())).first()
            if duplicate:
                raise TrashConflictError("user_identity_conflict")
            before = {"is_active": entity.is_active, "trashed_at": entity.trashed_at, "auth_version": entity.auth_version}
            entity.is_active = True
            entity.trashed_at = None
            entity.auth_version += 1
            after = {"is_active": True, "trashed_at": None, "auth_version": entity.auth_version}
            history_type = "user"
        entry.state = "restored"
        entry.restored_at = now
        entry.restored_by_user_id = actor.id
        entry.last_error_code = None
        self.db.add(entity)
        self.db.add(entry)
        self.db.flush()
        self.history.persist(
            actor_user_id=actor.id, entity_type=history_type, entity_id=entry.entity_id,
            action="restored", before=before, after=after,
            source_key=f"trash:{entry.id}:restored",
        )
        return entry

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def purge_locked(self, entry: TrashEntry) -> tuple[str, list[_MovedFile]]:
        now = self._now()
        if entry.state not in ("trashed", "blocked") or now < entry.purge_after:
            return "skipped", []
        entry.state = "purging"
        entry.purge_started_at = now
        entry.attempt_count += 1
        self.db.flush()
        if entry.entity_type == "document":
            moves, vector_points_deleted = self._purge_document(entry, now)
            history_type = "document"
        elif entry.entity_type == "client":
            moves = []
            self._purge_client(entry, now)
            history_type = "client"
        else:
            moves = []
            self._purge_user(entry, now)
            history_type = "user"
        entry.state = "purged"
        entry.purged_at = now
        entry.last_error_code = None
        self.history.persist(
            actor_user_id=None, entity_type=history_type, entity_id=entry.entity_id,
            action="purged", before={"purged_at": None}, after={
                "purged_at": now,
                **(
                    {
                        "vector_points_deleted_count": vector_points_deleted,
                        "vector_collection": self.vector_store.collection_name,
                        "purge_result": "purged",
                    }
                    if entry.entity_type == "document"
                    else {}
                ),
            },
            source_key=f"trash:{entry.id}:purged",
        )
        return "purged", moves

    def _purge_document(self, entry: TrashEntry, now: datetime) -> tuple[list[_MovedFile], int]:
        document = self.db.query(Document).filter(Document.id == entry.entity_id).with_for_update().first()
        if document is None or document.trashed_at is None or document.purged_at is not None:
            raise TrashPurgeBlockedError("document_state_mismatch")
        if self.db.query(Document.id).filter(Document.parent_document_id == document.id, Document.purged_at.is_(None)).first():
            raise TrashPurgeBlockedError("archive_family_not_safe")
        if document.processing_status in ("extracting",) or document.vision_status in ("pending", "queued", "processing"):
            raise TrashPurgeBlockedError("document_processing_active")
        paths: list[Path] = []
        if document.storage_path:
            try:
                original = resolve_document_storage_path(
                    storage_path=document.storage_path,
                    data_root=self.data_root,
                )
            except (DocumentContentUnavailableError, UnsafeDocumentStoragePathError) as error:
                raise TrashPurgeBlockedError("unsafe_document_storage_path") from error
            if document.checksum_sha256 and self._sha256(original) != document.checksum_sha256.lower():
                raise TrashPurgeBlockedError("document_checksum_mismatch")
            paths.append(original)
        for value in self.db.query(DocumentPage.render_path).filter(DocumentPage.document_id == document.id, DocumentPage.render_path.is_not(None)):
            try:
                paths.append(resolve_document_storage_path(storage_path=value[0], data_root=self.data_root))
            except (DocumentContentUnavailableError, UnsafeDocumentStoragePathError) as error:
                raise TrashPurgeBlockedError("unsafe_document_storage_path") from error
        for value in self.db.query(DocumentAsset.storage_path).filter(DocumentAsset.document_id == document.id):
            try:
                paths.append(resolve_document_storage_path(storage_path=value[0], data_root=self.data_root))
            except (DocumentContentUnavailableError, UnsafeDocumentStoragePathError) as error:
                raise TrashPurgeBlockedError("unsafe_document_storage_path") from error
        chunk_rows = (
            self.db.query(
                DocumentChunk.id,
                DocumentChunk.vector_id,
                DocumentChunk.embedding_version,
            )
            .filter(
                DocumentChunk.document_id == document.id,
                DocumentChunk.vector_id.is_not(None),
            )
            .order_by(DocumentChunk.id.asc())
            .all()
        )
        references = [
            DocumentVectorReference(
                vector_id=str(vector_id),
                chunk_id=chunk_id,
                embedding_version=embedding_version,
            )
            for chunk_id, vector_id, embedding_version in chunk_rows
        ]
        try:
            vector_plan = self.vector_store.prepare_document_purge(
                document_id=document.id,
                references=references,
            )
        except QdrantDocumentPurgeError as error:
            raise TrashPurgeBlockedError(error.code) from error
        except Exception as error:
            raise TrashPurgeBlockedError("qdrant_preflight_unavailable") from error
        try:
            vector_points_deleted = self.vector_store.delete_document_points(vector_plan)
        except QdrantDocumentPurgeError as error:
            raise TrashPurgeBlockedError(error.code) from error
        except Exception as error:
            raise TrashPurgeBlockedError("qdrant_delete_failed") from error
        quarantine_root = (self.data_root / ".trash-quarantine" / str(entry.id)).resolve()
        if self.data_root not in quarantine_root.parents:
            raise TrashPurgeBlockedError("unsafe_quarantine_path")
        quarantine_root.mkdir(parents=True, exist_ok=True)
        moves: list[_MovedFile] = []
        try:
            for index, source in enumerate(dict.fromkeys(paths)):
                target = quarantine_root / f"{index:04d}.bin"
                source.replace(target)
                moves.append(_MovedFile(source=source, quarantine=target))
            self.db.query(DocumentPage).filter(DocumentPage.document_id == document.id).delete(synchronize_session=False)
            self.db.query(DocumentAsset).filter(DocumentAsset.document_id == document.id).delete(synchronize_session=False)
            self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete(synchronize_session=False)
            document.filename = f"deleted-document-{document.id}"
            document.original_filename = None
            document.content_type = "application/x-deleted"
            document.file_size = 0
            document.storage_path = None
            document.checksum_sha256 = None
            document.extracted_text = None
            document.metadata_raw = None
            document.metadata_normalized = None
            document.metadata_error = None
            document.processing_error = None
            document.latitude = document.longitude = document.location_accuracy_m = None
            document.location_source = None
            document.vision_classification = None
            document.vision_error_code = None
            document.vision_source_checksum = None
            document.purged_at = now
            self.db.add(document)
            return moves, vector_points_deleted
        except Exception:
            for item in reversed(moves):
                if item.quarantine.exists() and not item.source.exists():
                    item.source.parent.mkdir(parents=True, exist_ok=True)
                    item.quarantine.replace(item.source)
            shutil.rmtree(quarantine_root, ignore_errors=True)
            raise

    def _purge_client(self, entry: TrashEntry, now: datetime) -> None:
        client = self.db.query(Client).filter(Client.id == entry.entity_id).with_for_update().first()
        if client is None or client.deleted_at is None or client.purged_at is not None:
            raise TrashPurgeBlockedError("client_state_mismatch")
        client.name = f"Usunięty klient #{client.id}"
        for field in ("legal_name", "tax_id", "registration_number", "website", "primary_email", "primary_phone", "street", "building_number", "unit_number", "postal_code", "city", "notes"):
            setattr(client, field, None)
        client.industry_id = None
        client.purged_at = now
        for contact in self.db.query(ClientContactPoint).filter(ClientContactPoint.client_id == client.id).with_for_update().all():
            contact.value = f"deleted-contact-{contact.id}"
            contact.normalized_value = f"deleted-contact-{contact.id}"
            contact.deleted_at = contact.deleted_at or now
        for address in self.db.query(ClientAddress).filter(ClientAddress.client_id == client.id).with_for_update().all():
            address.label = "Usunięty adres"
            for field in ("street", "building_number", "unit_number", "postal_code", "city"):
                setattr(address, field, None)
            address.deleted_at = address.deleted_at or now
        self.db.add(client)

    def _purge_user(self, entry: TrashEntry, now: datetime) -> None:
        self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": USER_LIFECYCLE_ADVISORY_LOCK_KEY})
        user = self.db.query(User).filter(User.id == entry.entity_id).with_for_update().first()
        if user is None or user.trashed_at is None or user.purged_at is not None or user.is_active:
            raise TrashPurgeBlockedError("user_state_mismatch")
        suffix = secrets.token_hex(6)
        user.username = f"deleted-user-{user.id}-{suffix}"[:50]
        user.email = f"deleted-user-{user.id}-{suffix}@deleted.invalid"
        user.password_hash = hash_password(secrets.token_urlsafe(48))
        user.must_change_password = False
        user.password_reset_requested = False
        user.auth_version += 1
        user.purged_at = now
        self.db.add(user)


class TrashPurgeRunner:
    def __init__(self, *, batch_limit: int = 100, data_root: Path | None = None) -> None:
        self.batch_limit = min(max(batch_limit, 1), 100)
        self.data_root = data_root

    def run(self) -> dict[str, int | bool]:
        lock_db = SessionLocal()
        summary: dict[str, int | bool] = {"eligible": 0, "processed": 0, "purged": 0, "blocked": 0, "failed": 0, "singleton_acquired": False}
        try:
            acquired = bool(lock_db.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": TRASH_PURGE_ADVISORY_LOCK_KEY}).scalar())
            summary["singleton_acquired"] = acquired
            if not acquired:
                return summary
            ids = [
                row[0]
                for row in lock_db.query(TrashEntry.id)
                .filter(
                    (
                        TrashEntry.state.in_(("trashed", "blocked"))
                        & (TrashEntry.purge_after <= func.transaction_timestamp())
                    )
                    | (
                        (TrashEntry.state == "purged")
                        & (TrashEntry.last_error_code == "quarantine_cleanup_required")
                    )
                )
                .order_by(TrashEntry.purge_after, TrashEntry.id)
                .limit(self.batch_limit)
                .all()
            ]
            summary["eligible"] = len(ids)
            for entry_id in ids:
                db = SessionLocal()
                moved: list[_MovedFile] = []
                try:
                    entry = db.query(TrashEntry).filter(TrashEntry.id == entry_id).with_for_update().first()
                    if entry is None:
                        continue
                    if (
                        entry.state == "purged"
                        and entry.last_error_code == "quarantine_cleanup_required"
                    ):
                        quarantine = (
                            (self.data_root or Path(settings.data_dir)).resolve()
                            / ".trash-quarantine"
                            / str(entry.id)
                        )
                        if quarantine.exists():
                            shutil.rmtree(quarantine)
                        entry.last_error_code = None
                        db.commit()
                        continue
                    result, moved = TrashLifecycleService(db, data_root=self.data_root).purge_locked(entry)
                    if result == "skipped":
                        db.rollback()
                        continue
                    db.commit()
                    summary["purged"] = int(summary["purged"]) + 1
                    if moved:
                        try:
                            shutil.rmtree(moved[0].quarantine.parent)
                        except Exception:
                            entry.last_error_code = "quarantine_cleanup_required"
                            db.add(entry)
                            db.commit()
                            summary["failed"] = int(summary["failed"]) + 1
                except TrashPurgeBlockedError as error:
                    db.rollback()
                    entry = db.query(TrashEntry).filter(TrashEntry.id == entry_id).with_for_update().first()
                    if entry is not None and entry.state in ACTIVE_STATES:
                        entry.state = "blocked"
                        entry.attempt_count += 1
                        entry.last_error_code = error.code
                        db.commit()
                    summary["blocked"] = int(summary["blocked"]) + 1
                except Exception:
                    db.rollback()
                    for item in reversed(moved):
                        if item.quarantine.exists() and not item.source.exists():
                            item.source.parent.mkdir(parents=True, exist_ok=True)
                            item.quarantine.replace(item.source)
                    summary["failed"] = int(summary["failed"]) + 1
                finally:
                    summary["processed"] = int(summary["processed"]) + 1
                    db.close()
            return summary
        finally:
            if summary["singleton_acquired"]:
                lock_db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": TRASH_PURGE_ADVISORY_LOCK_KEY})
            lock_db.close()
