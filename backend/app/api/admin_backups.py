import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.admin_users import require_admin
from app.database.session import get_db
from app.models.backup_operation import BackupRun, BackupSchedule, ManagedBackup, RestoreRun
from app.models.user import User
from app.schemas.admin_backup import (
    BackupRunPage,
    BackupRunRead,
    BackupRunRequest,
    BackupReconcileResult,
    BackupScheduleRead,
    BackupScheduleWrite,
    HostStorageBrowseRequest,
    HostStorageBrowseResult,
    HostStorageLocation,
    HostStorageRegisterRequest,
    ManagedBackupDeleteRequest,
    ManagedBackupRead,
    LegacyBackupAdoptRequest,
    LegacyBackupAdoptResult,
    LegacyBackupCandidate,
    LegacyVerificationJob,
    LegacyVerificationStartRequest,
    LegacyVerificationStatusRequest,
    ManualBackupPreflight,
    ManualBackupPreflightRequest,
    ManualBackupStartRequest,
    ManualBackupV3PreflightRequest,
    ManualBackupV3StartRequest,
    RetentionPreview,
    RestoreCandidate,
    RestorePreview,
    RestorePreviewRequest,
    RestoreRequest,
    RestoreRunRead,
)
from app.services.backup_restore_service import (
    BackupRestoreConflict,
    BackupRestoreService,
    BackupRestoreValidation,
)
from app.services.backup_supervisor_client import (
    BackupSupervisorRejected,
    BackupSupervisorUnavailable,
)

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/admin/backups", tags=["Admin Backup Restore"])


def map_error(error: Exception) -> HTTPException:
    code = str(error)
    if isinstance(error, BackupSupervisorUnavailable):
        return HTTPException(status_code=503, detail={"code": "backup_supervisor_unavailable"})
    if isinstance(error, BackupSupervisorRejected):
        return HTTPException(status_code=409, detail={"code": error.code})
    if isinstance(error, BackupRestoreConflict):
        return HTTPException(status_code=409, detail={"code": code})
    return HTTPException(status_code=422, detail={"code": code})


@router.get("/schedules", response_model=list[BackupScheduleRead])
def list_schedules(
    _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[BackupScheduleRead]:
    return [BackupScheduleRead.model_validate(item) for item in BackupRestoreService(db).schedule_views()]


@router.post("/schedules", response_model=BackupScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: BackupScheduleWrite,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BackupScheduleRead:
    try:
        service = BackupRestoreService(db)
        item = service.create_schedule(payload, actor)
        db.commit(); db.refresh(item)
        return BackupScheduleRead.model_validate(next(view for view in service.schedule_views() if view["id"] == item.id))
    except (BackupRestoreConflict, BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        db.rollback(); raise map_error(error) from error
    except IntegrityError as error:
        db.rollback(); raise HTTPException(status_code=409, detail={"code": "backup_schedule_name_conflict"}) from error


@router.put("/schedules/{schedule_id}", response_model=BackupScheduleRead)
def update_schedule(
    schedule_id: int,
    payload: BackupScheduleWrite,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BackupScheduleRead:
    item = db.get(BackupSchedule, schedule_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "backup_schedule_not_found"})
    try:
        service = BackupRestoreService(db)
        item = service.update_schedule(item, payload, actor)
        db.commit(); db.refresh(item)
        return BackupScheduleRead.model_validate(next(view for view in service.schedule_views() if view["id"] == item.id))
    except (BackupRestoreConflict, BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        db.rollback(); raise map_error(error) from error
    except IntegrityError as error:
        db.rollback(); raise HTTPException(status_code=409, detail={"code": "backup_schedule_name_conflict"}) from error


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    item = db.get(BackupSchedule, schedule_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "backup_schedule_not_found"})
    service = BackupRestoreService(db)
    try:
        service.delete_schedule(item)
        db.commit()
    except (BackupRestoreConflict, BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        db.rollback(); raise map_error(error) from error


@router.post("/schedules/reconcile", response_model=BackupReconcileResult)
def reconcile_schedules(
    _: User = Depends(require_admin), db: Session = Depends(get_db),
) -> BackupReconcileResult:
    try:
        return BackupReconcileResult.model_validate(BackupRestoreService(db).reconcile_pending())
    except (BackupRestoreConflict, BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        db.rollback(); raise map_error(error) from error


@router.post("/run", response_model=BackupRunRead, status_code=status.HTTP_202_ACCEPTED)
def run_backup(
    payload: BackupRunRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BackupRunRead:
    if not payload.confirmed:
        raise HTTPException(status_code=422, detail={"code": "backup_confirmation_required"})
    try:
        run = BackupRestoreService(db).start_backup(
            scope=payload.scope, destination=payload.destination, actor=actor
        )
        db.commit(); db.refresh(run)
        return BackupRunRead.model_validate(run)
    except (BackupRestoreConflict, BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        db.rollback(); raise map_error(error) from error


@router.post("/manual-v2/preflight", response_model=ManualBackupPreflight)
def manual_backup_preflight(
    payload: ManualBackupPreflightRequest,
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> ManualBackupPreflight:
    try:
        token, expires, host = BackupRestoreService(db).issue_preflight_token(
            user_id=actor.id, scope=payload.scope, destination=payload.destination
        )
        return ManualBackupPreflight(
            normalized_destination=host["normalized_destination"],
            available=bool(host["available"]), writable=bool(host["writable"]),
            total_bytes=int(host.get("total_bytes") or 0), free_bytes=int(host.get("free_bytes") or 0),
            estimated_required_bytes=host.get("estimated_required_bytes"), token=token, expires_at=expires,
        )
    except (BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        raise map_error(error) from error


@router.post("/manual-v2/run", response_model=BackupRunRead, status_code=status.HTTP_202_ACCEPTED)
def run_manual_backup_v2(
    payload: ManualBackupStartRequest,
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> BackupRunRead:
    if not payload.confirmed:
        raise HTTPException(status_code=422, detail={"code": "backup_confirmation_required"})
    try:
        service = BackupRestoreService(db)
        destination = service.verify_preflight_token(
            token=payload.preflight_token, user_id=actor.id, scope=payload.scope, destination=payload.destination
        )
        run = service.start_backup(scope=payload.scope, destination=destination, actor=actor)
        db.commit(); db.refresh(run)
        return BackupRunRead.model_validate(run)
    except (BackupRestoreConflict, BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        db.rollback(); raise map_error(error) from error


@router.get("/storage-locations", response_model=list[HostStorageLocation])
def host_storage_locations(
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> list[HostStorageLocation]:
    try:
        return [
            HostStorageLocation.model_validate(item)
            for item in BackupRestoreService(db).host_storage_locations(actor)
        ]
    except (BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        raise map_error(error) from error


@router.post("/storage-locations/register", response_model=HostStorageLocation)
def register_host_storage(
    payload: HostStorageRegisterRequest,
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> HostStorageLocation:
    try:
        return HostStorageLocation.model_validate(
            BackupRestoreService(db).register_host_storage(
                actor=actor, host_path=payload.host_path
            )
        )
    except (BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        raise map_error(error) from error


@router.post("/storage-locations/browse", response_model=HostStorageBrowseResult)
def browse_host_storage(
    payload: HostStorageBrowseRequest,
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> HostStorageBrowseResult:
    try:
        return HostStorageBrowseResult.model_validate(
            BackupRestoreService(db).browse_host_storage(
                actor=actor,
                location_token=payload.location_token,
                relative_path=payload.relative_path,
            )
        )
    except (BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        raise map_error(error) from error


@router.post("/manual-v3/preflight", response_model=ManualBackupPreflight)
def manual_backup_v3_preflight(
    payload: ManualBackupV3PreflightRequest,
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> ManualBackupPreflight:
    try:
        token, expires, host = BackupRestoreService(db).issue_v3_preflight(
            actor=actor,
            scope=payload.scope,
            location_token=payload.location_token,
            relative_path=payload.relative_path,
        )
        return ManualBackupPreflight(
            normalized_destination=host["normalized_destination"],
            destination_display=host["normalized_destination"],
            storage_location_id=BackupRestoreService._location_id(
                host["normalized_destination"]
            ),
            available=bool(host["available"]),
            writable=bool(host["writable"]),
            total_bytes=int(host.get("total_bytes") or 0),
            free_bytes=int(host.get("free_bytes") or 0),
            estimated_required_bytes=host.get("estimated_required_bytes"),
            predicted_free_bytes=host.get("predicted_free_bytes"),
            reserve_required_bytes=int(host.get("reserve_required_bytes") or 0),
            retention_impact=str(host.get("retention_impact") or "not_applicable"),
            token=token,
            expires_at=expires,
        )
    except (BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        raise map_error(error) from error


@router.post("/manual-v3/run", response_model=BackupRunRead, status_code=status.HTTP_202_ACCEPTED)
def run_manual_backup_v3(
    payload: ManualBackupV3StartRequest,
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> BackupRunRead:
    if not payload.confirmed:
        raise HTTPException(status_code=422, detail={"code": "backup_confirmation_required"})
    try:
        service = BackupRestoreService(db)
        destination = service.verify_preflight_token_v3(
            token=payload.preflight_token,
            user_id=actor.id,
            scope=payload.scope,
        )
        run = service.start_backup(
            scope=payload.scope, destination=destination, actor=actor
        )
        db.commit(); db.refresh(run)
        return BackupRunRead.model_validate(run)
    except (BackupRestoreConflict, BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        db.rollback(); raise map_error(error) from error


@router.get("/managed", response_model=list[ManagedBackupRead])
def managed_backups(
    _: User = Depends(require_admin), db: Session = Depends(get_db),
) -> list[ManagedBackupRead]:
    return [ManagedBackupRead.model_validate(item) for item in BackupRestoreService(db).list_managed_backups()]


@router.get("/legacy-candidates", response_model=list[LegacyBackupCandidate])
def legacy_backup_candidates(
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> list[LegacyBackupCandidate]:
    try:
        return [
            LegacyBackupCandidate.model_validate(item)
            for item in BackupRestoreService(db).legacy_candidates(actor)
        ]
    except (BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        raise map_error(error) from error


@router.post("/legacy-adopt", response_model=LegacyBackupAdoptResult)
def adopt_legacy_backup(
    payload: LegacyBackupAdoptRequest,
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> LegacyBackupAdoptResult:
    if not payload.confirmed:
        raise HTTPException(status_code=422, detail={"code": "legacy_adoption_confirmation_required"})
    try:
        managed, existing = BackupRestoreService(db).adopt_legacy_backup(
            token=payload.adoption_token, plan_id=payload.plan_id, actor=actor
        )
        db.commit(); db.refresh(managed)
        logger.info(
            "legacy_backup_catalog_adoption user_id=%s managed_backup_id=%s existing=%s",
            actor.id,
            managed.id,
            existing,
        )
        return LegacyBackupAdoptResult(
            managed_backup=ManagedBackupRead.model_validate(managed),
            already_managed=existing,
        )
    except (BackupRestoreConflict, BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        db.rollback(); raise map_error(error) from error
    except IntegrityError as error:
        db.rollback(); raise HTTPException(status_code=409, detail={"code": "legacy_adoption_duplicate"}) from error


@router.post(
    "/legacy-verifications",
    response_model=LegacyVerificationJob,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_legacy_verification(
    payload: LegacyVerificationStartRequest,
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> LegacyVerificationJob:
    if not payload.confirmed:
        raise HTTPException(status_code=422, detail={"code": "legacy_adoption_confirmation_required"})
    try:
        return LegacyVerificationJob.model_validate(
            BackupRestoreService(db).start_legacy_verification(
                token=payload.adoption_token,
                plan_id=payload.plan_id,
                actor=actor,
            )
        )
    except (BackupRestoreConflict, BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        raise map_error(error) from error


@router.post("/legacy-verifications/status", response_model=LegacyVerificationJob)
def legacy_verification_status(
    payload: LegacyVerificationStatusRequest,
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> LegacyVerificationJob:
    try:
        result = BackupRestoreService(db).legacy_verification_status(
            job_token=payload.job_token, actor=actor
        )
        if result.get("state") == "SUCCEEDED":
            db.commit()
            managed = result.get("managed_backup")
            if managed is not None:
                db.refresh(managed)
        return LegacyVerificationJob.model_validate(result)
    except (BackupRestoreConflict, BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        db.rollback(); raise map_error(error) from error
    except IntegrityError as error:
        db.rollback(); raise HTTPException(status_code=409, detail={"code": "legacy_adoption_duplicate"}) from error


@router.post("/legacy-verifications/cancel", response_model=LegacyVerificationJob)
def cancel_legacy_verification(
    payload: LegacyVerificationStatusRequest,
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> LegacyVerificationJob:
    try:
        return LegacyVerificationJob.model_validate(
            BackupRestoreService(db).cancel_legacy_verification(
                job_token=payload.job_token, actor=actor
            )
        )
    except (BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        raise map_error(error) from error


@router.get("/schedules/{schedule_id}/retention-preview", response_model=RetentionPreview)
def retention_preview(
    schedule_id: int, predicted_backup_bytes: int = Query(0, ge=0),
    _: User = Depends(require_admin), db: Session = Depends(get_db),
) -> RetentionPreview:
    item = db.get(BackupSchedule, schedule_id)
    if item is None or item.deleted_at is not None:
        raise HTTPException(status_code=404, detail={"code": "backup_schedule_not_found"})
    try:
        return RetentionPreview.model_validate(BackupRestoreService(db).retention_preview(item, predicted_backup_bytes))
    except (BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        raise map_error(error) from error


@router.post("/managed/{managed_backup_id}/delete", status_code=status.HTTP_202_ACCEPTED)
def delete_managed_backup(
    managed_backup_id: int, payload: ManagedBackupDeleteRequest,
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> dict:
    if not payload.confirmed or payload.confirmation != "USUŃ BACKUP":
        raise HTTPException(status_code=422, detail={"code": "managed_backup_confirmation_required"})
    item = db.get(ManagedBackup, managed_backup_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "managed_backup_not_found"})
    try:
        event = BackupRestoreService(db).delete_managed_backup(item, actor)
        db.commit(); db.refresh(event)
        return {"event_id": event.id, "status": event.status, "actual_reclaimed_bytes": event.actual_reclaimed_bytes}
    except (BackupRestoreConflict, BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        db.commit()
        raise map_error(error) from error


@router.get("/runs", response_model=BackupRunPage)
def list_runs(
    skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin), db: Session = Depends(get_db),
) -> BackupRunPage:
    query = db.query(BackupRun)
    total = query.count()
    items = query.order_by(BackupRun.started_at.desc(), BackupRun.id.desc()).offset(skip).limit(limit).all()
    service = BackupRestoreService(db)
    for item in items:
        try:
            service.refresh_run(item)
        except (BackupSupervisorUnavailable, BackupSupervisorRejected):
            pass
    db.commit()
    return BackupRunPage(items=[BackupRunRead.model_validate(item) for item in items], total=total, skip=skip, limit=limit)


@router.get("/restore-candidates", response_model=list[RestoreCandidate])
def restore_candidates(
    _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[RestoreCandidate]:
    try:
        return BackupRestoreService(db).discover()
    except (BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        raise map_error(error) from error


@router.post("/restore-preview", response_model=RestorePreview)
def restore_preview(
    payload: RestorePreviewRequest,
    _: User = Depends(require_admin), db: Session = Depends(get_db),
) -> RestorePreview:
    revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    try:
        return RestorePreview.model_validate(
            BackupRestoreService(db).preview(payload.checkpoint_path, payload.mode, revision)
        )
    except (BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        raise map_error(error) from error


@router.post("/restore", response_model=RestoreRunRead, status_code=status.HTTP_202_ACCEPTED)
def request_restore(
    payload: RestoreRequest,
    actor: User = Depends(require_admin), db: Session = Depends(get_db),
) -> RestoreRunRead:
    revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    try:
        run = BackupRestoreService(db).request_restore(
            checkpoint_path=payload.checkpoint_path,
            mode=payload.mode,
            acknowledged=payload.acknowledged,
            confirmation=payload.confirmation,
            actor=actor,
            current_revision=revision,
        )
        db.commit(); db.refresh(run)
        return RestoreRunRead.model_validate(run)
    except (BackupRestoreConflict, BackupRestoreValidation, BackupSupervisorUnavailable, BackupSupervisorRejected) as error:
        db.rollback(); raise map_error(error) from error


@router.get("/restores", response_model=list[RestoreRunRead])
def list_restores(
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin), db: Session = Depends(get_db),
) -> list[RestoreRunRead]:
    items = db.query(RestoreRun).order_by(RestoreRun.started_at.desc(), RestoreRun.id.desc()).limit(limit).all()
    return [RestoreRunRead.model_validate(item) for item in items]


@router.get("/restores/{restore_id}", response_model=RestoreRunRead)
def get_restore(
    restore_id: int,
    _: User = Depends(require_admin), db: Session = Depends(get_db),
) -> RestoreRunRead:
    item = db.get(RestoreRun, restore_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "restore_run_not_found"})
    return RestoreRunRead.model_validate(item)
