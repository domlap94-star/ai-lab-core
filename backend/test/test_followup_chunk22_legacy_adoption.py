from __future__ import annotations

from datetime import datetime, timezone

from app.database.session import SessionLocal
from app.models.backup_operation import ManagedBackup
from app.models.user import User
from app.services.backup_restore_service import (
    BackupRestoreService,
    BackupRestoreValidation,
)
from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()


class FakeSupervisor:
    def __init__(self) -> None:
        self.manifest_hash = "a" * 64

    def discover(self, destinations, *, include_invalid=False):
        root = destinations[0]
        return {
            "items": [
                {
                    "checkpoint_path": root + r"\20260820T030000Z",
                    "destination_root": root,
                    "created_at": "2026-08-20T03:00:00+00:00",
                    "scope": "database",
                    "app_version": "1.0.2+25",
                    "source_head": "b" * 40,
                    "db_revision": "followup_contact_person_20260822",
                    "total_bytes": 1234,
                    "verified": True,
                    "artifact_count": 1,
                    "manifest_path": root + r"\20260820T030000Z\backup-manifest.json",
                    "manifest_schema": "NEXT_STABIL_BACKUP_V1",
                    "manifest_sha256": self.manifest_hash,
                }
            ]
        }

    def inventory(self, destinations, *, include_invalid=False):
        payload = self.discover(destinations, include_invalid=include_invalid)
        return {
            "items": [
                {
                    **item,
                    "verified": False,
                    "error_code": "checkpoint_verification_required",
                }
                for item in payload["items"]
            ]
        }

    def verify_checkpoint(self, destination_root, checkpoint_path):
        return self.discover([destination_root])["items"][0]


def expect_code(call, code: str) -> None:
    try:
        call()
    except BackupRestoreValidation as error:
        assert str(error) == code
    else:
        raise AssertionError(f"expected {code}")


def main() -> None:
    fake = FakeSupervisor()
    with SessionLocal() as db:
        assert_isolated_database(db, TEST_DATABASE_NAME)
        db.query(ManagedBackup).filter(ManagedBackup.backup_id.like("legacy-%")).delete()
        db.commit()
        actor = db.get(User, 900001)
        assert actor is not None
        service = BackupRestoreService(db, fake)

        candidates = service.legacy_candidates(actor)
        candidate = next(item for item in candidates if item["adoptable"])
        assert not candidate["verified"] and candidate["manifest_schema"] == "NEXT_STABIL_BACKUP_V1"
        assert candidate["adoption_token"] and candidate["already_managed"] is False

        adopted, existed = service.adopt_legacy_backup(
            token=candidate["adoption_token"], plan_id=None, actor=actor
        )
        db.commit(); db.refresh(adopted)
        assert existed is False and adopted.plan_id is None
        assert adopted.checkpoint_path.endswith("20260820T030000Z")
        assert adopted.manifest_sha256 == "a" * 64

        repeated, existed = service.adopt_legacy_backup(
            token=candidate["adoption_token"], plan_id=None, actor=actor
        )
        assert existed is True and repeated.id == adopted.id
        assert db.query(ManagedBackup).filter_by(checkpoint_path=adopted.checkpoint_path).count() == 1

        fake.manifest_hash = "c" * 64
        expect_code(
            lambda: service.adopt_legacy_backup(
                token=candidate["adoption_token"], plan_id=None, actor=actor
            ),
            "legacy_adoption_manifest_changed",
        )
        db.rollback()
        db.delete(adopted); db.commit()
        print("LEGACY_BACKUP_ADOPTION_ISOLATED_TESTS=PASS")


if __name__ == "__main__":
    main()
