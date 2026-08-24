from __future__ import annotations

from datetime import datetime, timezone

from app.database.session import SessionLocal
from app.models.backup_operation import ManagedBackup
from app.models.role import Role
from app.models.user import User
from app.services.backup_restore_service import (
    BackupRestoreService,
    BackupRestoreValidation,
)
from app.services.backup_supervisor_client import BackupSupervisorRejected
from test.support.database_safety import (
    assert_isolated_database,
    require_test_database_environment,
)


TEST_DATABASE_NAME = require_test_database_environment()


class FakeSupervisor:
    def __init__(self) -> None:
        self.manifest_hash = "a" * 64
        self.missing_job = False

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

    def start_legacy_verification(self, *, job_id, destination_root, checkpoint_path):
        self.job_id = job_id
        return {
            "job_id": job_id,
            "state": "QUEUED",
            "files_checked": 0,
            "files_total": 1,
            "bytes_checked": 0,
            "bytes_total": 1234,
        }

    def legacy_verification_status(self, job_id):
        assert job_id == self.job_id
        if self.missing_job:
            raise BackupSupervisorRejected("legacy_verification_job_not_found")
        return {
            "job_id": job_id,
            "state": "READY_TO_ADOPT",
            "files_checked": 1,
            "files_total": 1,
            "bytes_checked": 1234,
            "bytes_total": 1234,
        }

    def cancel_legacy_verification(self, job_id):
        return {"job_id": job_id, "state": "CANCELLED"}

    def inspect_storage(self, destinations):
        return {
            "items": [
                {
                    "normalized_destination": value,
                    "available": True,
                    "writable": True,
                    "total_bytes": 10000,
                    "free_bytes": 8000,
                    "path_type": "local_path",
                }
                for value in destinations
            ]
        }

    def browse_storage(self, destination_root, relative_path):
        return {
            "relative_path": relative_path,
            "directories": [
                {
                    "name": "Daily",
                    "relative_path": (relative_path + r"\Daily").lstrip("\\"),
                }
            ],
        }

    def destination_preflight(self, destination):
        return {
            "normalized_destination": destination,
            "available": True,
            "writable": True,
            "total_bytes": 10000,
            "free_bytes": 8000,
        }


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
        if actor is None:
            role = db.query(Role).filter_by(name="admin").one_or_none()
            if role is None:
                role = Role(name="admin", description="Isolated test administrator")
                db.add(role)
                db.flush()
            actor = User(
                id=900001,
                username="chunk22-isolated-admin",
                email="chunk22-isolated-admin@example.invalid",
                password_hash="isolated-test-not-a-credential",
                role_id=role.id,
            )
            db.add(actor)
            db.commit()
        service = BackupRestoreService(db, fake)

        locations = service.host_storage_locations(actor)
        assert locations and locations[0]["location_id"].startswith("LOC_")
        assert locations[0]["display_label"] and "normalized_destination" not in locations[0]
        browsed = service.browse_host_storage(
            actor=actor,
            location_token=locations[0]["location_token"],
            relative_path="",
        )
        assert browsed["location_id"] == locations[0]["location_id"]
        assert browsed["directories"][0]["relative_path"] == "Daily"
        expect_code(
            lambda: service.browse_host_storage(
                actor=actor,
                location_token=locations[0]["location_token"],
                relative_path=r"..\Windows",
            ),
            "backup_destination_relative_path_invalid",
        )
        preflight_token, _, host = service.issue_v3_preflight(
            actor=actor,
            scope="database",
            location_token=locations[0]["location_token"],
            relative_path="Daily",
        )
        assert host["normalized_destination"].endswith(r"\Daily")
        assert service.verify_preflight_token_v3(
            token=preflight_token, user_id=actor.id, scope="database"
        ).endswith(r"\Daily")

        candidates = service.legacy_candidates(actor)
        candidate = next(item for item in candidates if item["adoptable"])
        assert not candidate["verified"] and candidate["manifest_schema"] == "NEXT_STABIL_BACKUP_V1"
        assert candidate["adoption_token"] and candidate["already_managed"] is False
        assert candidate["classification"] == "NEEDS_VERIFICATION"

        started = service.start_legacy_verification(
            token=candidate["adoption_token"], plan_id=None, actor=actor
        )
        assert started["state"] == "QUEUED" and started["job_token"]
        fake.missing_job = True
        interrupted = service.legacy_verification_status(
            job_token=started["job_token"], actor=actor
        )
        assert interrupted["state"] == "FAILED"
        assert interrupted["error_code"] == "legacy_verification_interrupted"
        assert interrupted["retryable"] is True
        fake.missing_job = False
        started = service.start_legacy_verification(
            token=candidate["adoption_token"], plan_id=None, actor=actor
        )
        completed = service.legacy_verification_status(
            job_token=started["job_token"], actor=actor
        )
        assert completed["state"] == "SUCCEEDED"
        adopted = completed["managed_backup"]
        db.commit(); db.refresh(adopted)
        assert adopted.plan_id is None
        assert adopted.checkpoint_path.endswith("20260820T030000Z")
        assert adopted.manifest_sha256 == "a" * 64

        repeated = service.legacy_verification_status(
            job_token=started["job_token"], actor=actor
        )
        assert repeated["state"] == "SUCCEEDED"
        assert repeated["managed_backup"].id == adopted.id
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
