from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.models.knowledge_base import AnalysisJob
from app.schemas.analysis import (
    AnalysisProvenance,
    AnalysisRequest,
    AnalysisSourceRef,
    TEMP_CHAT_RESULT_CONTRACT_V2,
)
from app.services.advanced_analysis_orchestrator import AdvancedAnalysisOrchestrator
from app.services.analysis_sanitizer import AnalysisSanitizer


class DatabaseStub:
    def flush(self) -> None:
        return None


class SupervisorStub:
    def get_job(self, _job_id: str) -> dict:
        return {"state": "COMPLETE"}


def request_for(analysis_id=None) -> AnalysisRequest:
    excerpt = "Wizyta nieodbyta; zdjęcia nie mają skali."
    return AnalysisRequest(
        analysis_id=analysis_id or uuid4(),
        analysis_type="technical_interpretation",
        source_domain="technical",
        source_refs=[AnalysisSourceRef(
            source_ref="S1", checksum_sha256=hashlib.sha256(excerpt.encode()).hexdigest(), excerpt=excerpt,
        )],
        problem_statement="Jakie działanie wykonać?",
        structured_inputs={
            "contract_version": TEMP_CHAT_RESULT_CONTRACT_V2,
            "claims": [{"kind": "FACT", "fact_handle": "F1", "source_handle": "S1", "statement": excerpt}],
            "requested_output": "Strict V2",
        },
        evidence=["S1"], sensitivity="public_reference",
        allowed_methods=["local_llm", "temporary_chat"],
        provenance=AnalysisProvenance(source_checksum="0" * 64),
    )


def job_for(request: AnalysisRequest, package_hash: str, external_job_id=None) -> AnalysisJob:
    return AnalysisJob(
        id=str(request.analysis_id), analysis_type=request.analysis_type,
        source_domain=request.source_domain, status="advanced_queued",
        decision="ESCALATE_TEMP_CHAT", sensitivity=request.sensitivity,
        processor_id="synthetic_v2_binding", processor_version="v2",
        input_fingerprint="1" * 64, sanitized_package_hash=package_hash,
        sanitized_package_size=1, external_job_id=external_job_id or str(uuid4()),
        reasoning_attempt_count=1, format_retry_count=0,
    )


def write_artifact(root: Path, job: AnalysisJob, parsed_v2: dict, *, manifest_overrides=None, artifact_overrides=None) -> None:
    output = root / "jobs" / str(job.external_job_id) / "output"
    output.mkdir(parents=True, exist_ok=True)
    raw_hash = "2" * 64
    artifact = {
        "schema_version": "NEXT_STABIL_TEMP_CHAT_RESULT_ARTIFACT_V2",
        "job_id": str(job.external_job_id), "request_id": str(job.id),
        "contract_version": TEMP_CHAT_RESULT_CONTRACT_V2,
        "worker_attempt": 1, "created_at": datetime.now(UTC).isoformat(),
        "raw_result_hash": raw_hash, "parsed_v2": parsed_v2,
        "validation_pending": True,
    }
    artifact.update(artifact_overrides or {})
    body = (json.dumps(artifact, ensure_ascii=False, indent=2) + "\n").encode()
    (output / "analysis.json").write_bytes(body)
    manifest = {
        "schema_version": "NEXT_STABIL_ANALYSIS_RESULT_MANIFEST_V2",
        "job_id": str(job.external_job_id), "request_id": str(job.id), "analysis_id": str(job.id),
        "package_sha256": job.sanitized_package_hash,
        "contract_version": TEMP_CHAT_RESULT_CONTRACT_V2,
        "worker_attempt": 1, "raw_result_hash": raw_hash,
        "output_sha256": hashlib.sha256(body).hexdigest(),
    }
    manifest.update(manifest_overrides or {})
    (output / "result_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def apply(root: Path, request: AnalysisRequest, job: AnalysisJob) -> str:
    orchestrator = AdvancedAnalysisOrchestrator(DatabaseStub(), supervisor=SupervisorStub())
    orchestrator.spool_root = root
    return orchestrator.apply_external(job=job, request=request)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="next-v2-binding-") as value:
        root = Path(value)
        request = request_for()
        package_hash = AnalysisSanitizer().sanitize(request).sha256
        valid = {"schema": TEMP_CHAT_RESULT_CONTRACT_V2,
                 "claims": [{"class": "FACT", "fact_handles": ["F1"], "tool_handles": [], "visual_handles": []}],
                 "contradictions": []}

        job = job_for(request, package_hash); write_artifact(root, job, valid)
        assert apply(root, request, job) == "accepted_advanced"

        wrong_job = job_for(request, package_hash); write_artifact(root, wrong_job, valid, manifest_overrides={"job_id": str(uuid4())})
        assert apply(root, request, wrong_job) == "failed" and wrong_job.error_code == "analysis_result_manifest_binding_invalid"

        wrong_request = job_for(request, package_hash); write_artifact(root, wrong_request, valid, manifest_overrides={"request_id": str(uuid4())})
        assert apply(root, request, wrong_request) == "failed" and wrong_request.error_code == "analysis_v2_result_binding_invalid"

        legacy = job_for(request, package_hash); write_artifact(root, legacy, valid, artifact_overrides={"schema_version": "NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1"})
        assert apply(root, request, legacy) == "failed" and legacy.error_code == "analysis_v2_result_binding_invalid"

        unknown = job_for(request, package_hash)
        write_artifact(root, unknown, {**valid, "claims": [{"class": "FACT", "fact_handles": ["F9"], "tool_handles": [], "visual_handles": []}]})
        assert apply(root, request, unknown) == "failed" and unknown.error_code == "analysis_result_unknown_fact_handle"

        privacy = job_for(request, package_hash)
        write_artifact(root, privacy, {**valid, "leak": "marker.person@example.invalid"})
        assert apply(root, request, privacy) == "review_required" and privacy.error_code == "analysis_external_result_sensitive_data"

        partial = job_for(request, package_hash)
        output = root / "jobs" / str(partial.external_job_id) / "output"; output.mkdir(parents=True)
        (output / "analysis.json").write_text("{", encoding="utf-8")
        assert apply(root, request, partial) == "failed" and partial.error_code == "analysis_result_manifest_missing"

    print("TEMP_CHAT_V2_BACKEND_BINDING=PASS")


if __name__ == "__main__":
    main()
