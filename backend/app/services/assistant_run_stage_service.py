from __future__ import annotations

import socket
import os
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.assistant_pipeline import AssistantRun, AssistantRunStage
from app.schemas.assistant_pipeline import validate_bounded_json
from app.services.local_model_time_policy import phase_timeout_code


LEASE_SECONDS = 90


class AssistantRunStageService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_plan(self, run: AssistantRun, stages: tuple[dict, ...]) -> None:
        for item in stages:
            stage = AssistantRunStage(
                id=str(uuid.uuid4()),
                assistant_run_id=run.id,
                stage_key=item["stage_key"],
                stage_type=item["stage_type"],
                status="completed" if item["stage_type"] == "planning" else "queued",
                ordinal=item["ordinal"],
                inactivity_timeout_seconds=item["inactivity_timeout_seconds"],
                absolute_cap_seconds=item["absolute_cap_seconds"],
                started_at=datetime.now(UTC) if item["stage_type"] == "planning" else None,
                finished_at=datetime.now(UTC) if item["stage_type"] == "planning" else None,
                result_manifest={"planner": "deterministic"} if item["stage_type"] == "planning" else None,
            )
            self.db.add(stage)

    def latest(self, run_id: str, stage_type: str) -> AssistantRunStage | None:
        return self.db.query(AssistantRunStage).filter(
            AssistantRunStage.assistant_run_id == run_id,
            AssistantRunStage.stage_type == stage_type,
        ).order_by(AssistantRunStage.attempt.desc()).first()

    def start(self, run: AssistantRun, stage_type: str) -> AssistantRunStage:
        stage = self.latest(run.id, stage_type)
        if stage is None:
            raise ValueError("ASSISTANT_STAGE_NOT_PLANNED")
        if stage.status == "completed":
            return stage
        now = datetime.now(UTC)
        resumed_from_wait = stage.status == "waiting"
        stage.status = "running"
        # Durable resource/material waiting is not active compute. Restart the
        # active-stage clocks when this stage resumes after a wait.
        stage.started_at = now if resumed_from_wait else (stage.started_at or now)
        stage.heartbeat_at = now
        stage.last_progress_at = now if resumed_from_wait else (stage.last_progress_at or now)
        stage.lease_owner = f"{socket.gethostname()}:{os.getpid()}"
        stage.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        run.status = "running"
        run.current_stage = stage_type
        run.started_at = run.started_at or now
        run.heartbeat_at = now
        self.db.flush()
        return stage

    def progress(
        self,
        stage: AssistantRunStage,
        *,
        current: int | None = None,
        total: int | None = None,
        unit: str | None = None,
        manifest: dict | None = None,
        substantive: bool = True,
    ) -> None:
        now = datetime.now(UTC)
        stage.heartbeat_at = now
        stage.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        if substantive:
            stage.last_progress_at = now
        if current is not None:
            stage.progress_current = max(0, current)
        if total is not None:
            stage.progress_total = max(0, total)
        if unit is not None:
            stage.progress_unit = unit[:24]
        if manifest is not None:
            stage.result_manifest = validate_bounded_json(
                manifest, field_name="stage_result_manifest"
            )
        run = self.db.get(AssistantRun, stage.assistant_run_id)
        if run is not None:
            run.heartbeat_at = now
        self.db.flush()

    def wait(
        self,
        run: AssistantRun,
        stage_type: str,
        *,
        document_preparation_job_id: str | None = None,
        analysis_job_id: str | None = None,
        manifest: dict | None = None,
    ) -> AssistantRunStage:
        stage = self.latest(run.id, stage_type)
        if stage is None:
            raise ValueError("ASSISTANT_STAGE_NOT_PLANNED")
        now = datetime.now(UTC)
        stage.status = "waiting"
        stage.started_at = stage.started_at or now
        stage.heartbeat_at = now
        stage.last_progress_at = now
        stage.lease_owner = None
        stage.lease_expires_at = None
        stage.document_preparation_job_id = document_preparation_job_id
        stage.analysis_job_id = analysis_job_id
        if manifest is not None:
            stage.result_manifest = validate_bounded_json(
                manifest, field_name="stage_result_manifest"
            )
        run.status = "waiting"
        run.current_stage = stage_type
        run.heartbeat_at = now
        self.db.flush()
        return stage

    def complete(
        self,
        run: AssistantRun,
        stage_type: str,
        *,
        result_kind: str | None = None,
        result_manifest: dict | None = None,
        intelligence_artifact_id: str | None = None,
        analysis_job_id: str | None = None,
    ) -> AssistantRunStage:
        stage = self.latest(run.id, stage_type)
        if stage is None:
            raise ValueError("ASSISTANT_STAGE_NOT_PLANNED")
        now = datetime.now(UTC)
        stage.status = "completed"
        stage.finished_at = now
        stage.heartbeat_at = now
        stage.last_progress_at = now
        stage.lease_owner = None
        stage.lease_expires_at = None
        stage.result_kind = result_kind
        stage.intelligence_artifact_id = intelligence_artifact_id
        stage.analysis_job_id = analysis_job_id
        if result_manifest is not None:
            stage.result_manifest = validate_bounded_json(
                result_manifest, field_name="stage_result_manifest"
            )
        run.heartbeat_at = now
        self.db.flush()
        return stage

    def skip(self, run: AssistantRun, stage_type: str, reason: str) -> None:
        stage = self.latest(run.id, stage_type)
        if stage is None or stage.status in {"completed", "skipped"}:
            return
        stage.status = "skipped"
        stage.error_code = reason[:100]
        stage.finished_at = datetime.now(UTC)
        stage.lease_owner = None
        stage.lease_expires_at = None
        self.db.flush()

    def fail(self, run: AssistantRun, stage_type: str, error_code: str) -> None:
        stage = self.latest(run.id, stage_type)
        if stage is not None and stage.status not in {"completed", "skipped", "cancelled"}:
            stage.status = "failed"
            stage.error_code = error_code[:100]
            stage.finished_at = datetime.now(UTC)
            stage.lease_owner = None
            stage.lease_expires_at = None
        run.status = "failed"
        run.current_stage = None
        run.finished_at = datetime.now(UTC)
        self.db.flush()

    def cancel(self, run: AssistantRun) -> None:
        now = datetime.now(UTC)
        self.db.query(AssistantRunStage).filter(
            AssistantRunStage.assistant_run_id == run.id,
            AssistantRunStage.status.in_(["queued", "waiting", "running"]),
        ).update({
            AssistantRunStage.status: "cancelled",
            AssistantRunStage.finished_at: now,
            AssistantRunStage.lease_owner: None,
            AssistantRunStage.lease_expires_at: None,
        }, synchronize_session=False)
        run.status = "cancelled"
        run.current_stage = None
        run.cancel_requested_at = now
        run.finished_at = now
        self.db.flush()

    def recover_expired(self) -> int:
        now = datetime.now(UTC)
        rows = self.db.query(AssistantRunStage).filter(
            AssistantRunStage.status == "running",
            AssistantRunStage.lease_expires_at.is_not(None),
            AssistantRunStage.lease_expires_at < now,
        ).with_for_update(skip_locked=True).all()
        count = 0
        for stage in rows:
            run = self.db.get(AssistantRun, stage.assistant_run_id)
            if run is None or run.status == "cancelled":
                continue
            stage.status = "failed"
            stage.error_code = "STAGE_LEASE_EXPIRED"
            stage.finished_at = now
            stage.lease_owner = None
            stage.lease_expires_at = None
            if stage.attempt >= stage.max_attempts:
                run.status = "failed"
                run.current_stage = None
                run.finished_at = now
            else:
                retry = AssistantRunStage(
                    id=str(uuid.uuid4()),
                    assistant_run_id=stage.assistant_run_id,
                    stage_key=stage.stage_key,
                    stage_type=stage.stage_type,
                    status="queued",
                    ordinal=stage.ordinal,
                    attempt=stage.attempt + 1,
                    max_attempts=stage.max_attempts,
                    inactivity_timeout_seconds=stage.inactivity_timeout_seconds,
                    absolute_cap_seconds=stage.absolute_cap_seconds,
                )
                self.db.add(retry)
                run.status = "queued"
                run.current_stage = stage.stage_type
                run.recovery_generation += 1
            count += 1
        self.db.flush()
        return count

    def timeout_code(self, run_id: str) -> str | None:
        stage = self.db.query(AssistantRunStage).filter(
            AssistantRunStage.assistant_run_id == run_id,
            AssistantRunStage.status == "running",
        ).order_by(AssistantRunStage.ordinal, AssistantRunStage.attempt.desc()).first()
        if stage is None:
            return None
        now = datetime.now(UTC)
        started = stage.started_at or stage.created_at
        progress = stage.last_progress_at or started
        if (now - started).total_seconds() > stage.absolute_cap_seconds:
            return "STAGE_ABSOLUTE_TIMEOUT"
        if stage.stage_type in {"analyzing_local", "reducing_findings", "synthesizing"}:
            phase_code = phase_timeout_code(
                manifest=stage.result_manifest,
                last_progress_at=stage.last_progress_at,
                now=now,
            )
            if phase_code is not None:
                return phase_code
            phase_state = (stage.result_manifest or {}).get("local_model_phase")
            phase = phase_state.get("phase") if isinstance(phase_state, dict) else None
            if phase in {"model_load", "prompt_evaluation"}:
                return None
        if (now - progress).total_seconds() > stage.inactivity_timeout_seconds:
            return "STAGE_INACTIVITY_TIMEOUT"
        return None

    def retry_or_fail(self, run: AssistantRun, stage_type: str, error_code: str) -> bool:
        stage = self.latest(run.id, stage_type)
        if stage is None:
            self.fail(run, stage_type, error_code)
            return False
        now = datetime.now(UTC)
        stage.status = "failed"
        stage.error_code = error_code[:100]
        stage.finished_at = now
        stage.lease_owner = None
        stage.lease_expires_at = None
        if stage.attempt >= stage.max_attempts:
            run.status = "failed"
            run.current_stage = None
            run.finished_at = now
            self.db.flush()
            return False
        retry = AssistantRunStage(
            id=str(uuid.uuid4()),
            assistant_run_id=stage.assistant_run_id,
            stage_key=stage.stage_key,
            stage_type=stage.stage_type,
            status="queued",
            ordinal=stage.ordinal,
            attempt=stage.attempt + 1,
            max_attempts=stage.max_attempts,
            inactivity_timeout_seconds=stage.inactivity_timeout_seconds,
            absolute_cap_seconds=stage.absolute_cap_seconds,
        )
        self.db.add(retry)
        run.status = "queued"
        run.current_stage = stage.stage_type
        run.recovery_generation += 1
        self.db.flush()
        return True
