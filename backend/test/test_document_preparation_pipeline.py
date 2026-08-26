from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from pathlib import Path

from app.database.session import SessionLocal
from app.core.config import settings
from app.models.document_preparation_job import DocumentPreparationJob
from app.models.assistant_pipeline import AssistantRunMaterial
from app.models.role import Role
from app.models.user import User
from app.schemas.unified_assistant import UnifiedAssistantRequest, UnifiedAssistantResponse
from app.schemas.assistant_pipeline import AssistantRunCreateRequest
from app.services.assistant_run_dispatcher import _execute_run
from app.services.assistant_run_service import AssistantRunService
from app.services.document_preparation_dispatcher import _next_waiting_id, resume_waiting_analysis
from app.services.document_file_safety_service import DocumentFileSafetyService
from app.services.document_preparation_service import DocumentPreparationService
from app.services.document_intelligence_service import DocumentIntelligenceService
from app.services.document_service import DocumentService
from app.services.unified_assistant_service import UnifiedAssistantService
from test.support.database_safety import require_test_database_environment


class FileSafetyTests(unittest.TestCase):
    def test_signature_matrix_fails_closed(self) -> None:
        service = DocumentFileSafetyService()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "safe.pdf"; pdf.write_bytes(b"%PDF-1.4\n%%EOF")
            self.assertEqual(service.classify(path=pdf, original_filename=pdf.name, declared_mime="application/pdf").state, "supported")
            fake = root / "fake.pdf"; fake.write_bytes(b"plain text")
            self.assertEqual(service.classify(path=fake, original_filename=fake.name, declared_mime="application/pdf").state, "integrity_failed")
            exe = root / "report.pdf"; exe.write_bytes(b"MZ" + b"x" * 30)
            result = service.classify(path=exe, original_filename=exe.name, declared_mime="application/pdf")
            self.assertEqual(result.error_code, "EXECUTABLE_SIGNATURE_REJECTED")
            unsupported = root / "archive.rar"; unsupported.write_bytes(b"Rar!")
            self.assertEqual(service.classify(path=unsupported, original_filename=unsupported.name, declared_mime="application/octet-stream").state, "unsupported")
            text = root / "notes.csv"; text.write_text("a,b\n1,2\n", encoding="utf-8")
            self.assertEqual(service.classify(path=text, original_filename=text.name, declared_mime="text/csv").detected_format, "text")
            png = root / "photo.png"; png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 20)
            self.assertEqual(service.classify(path=png, original_filename=png.name, declared_mime="image/png").detected_format, "image")
            docx = root / "report.docx"
            with zipfile.ZipFile(docx, "w") as archive:
                archive.writestr("[Content_Types].xml", "<Types/>")
                archive.writestr("word/document.xml", "<document/>")
            self.assertEqual(service.classify(
                path=docx, original_filename=docx.name,
                declared_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ).detected_format, "docx")
            mismatch = service.classify(path=docx, original_filename=docx.name, declared_mime="image/png")
            self.assertEqual(mismatch.error_code, "MIME_EXTENSION_MISMATCH")


def integration_main() -> None:
    require_test_database_environment()
    previous_data_dir = settings.data_dir
    previous_v2 = settings.assistant_pipeline_v2_enabled
    isolated_storage = tempfile.TemporaryDirectory()
    settings.data_dir = isolated_storage.name
    settings.assistant_pipeline_v2_enabled = True
    db = SessionLocal()
    try:
        role = Role(id=900026, name="fileprep-test", description="isolated")
        user = User(id=900026, username="fileprep-test", email="fileprep@test.invalid", password_hash="not-used", role_id=role.id)
        db.add_all([role, user]); db.commit()
        stored = DocumentService(db).store_document(
            content=b"synthetic technical evidence for preparation",
            original_filename="synthetic.txt", content_type="text/plain",
            source_type="manual_upload", intake_metadata={"actor_user_id": user.id},
        )
        jobs = db.query(DocumentPreparationJob).filter_by(document_id=stored.document.id).all()
        assert len(jobs) == 1 and jobs[0].status == "queued"
        same, created = DocumentPreparationService(db).get_or_create(
            document=stored.document, trigger="assistant", priority=0, created_by_user_id=user.id
        )
        db.commit()
        assert not created and same.id == jobs[0].id and same.priority == 0

        request = UnifiedAssistantRequest(
            question="Przeanalizuj ten dokument", document_id=stored.document.id,
            attempt_id="isolated_attempt_20260826",
        )
        response = asyncio.run(UnifiedAssistantService(db).ask(request=request, user_id=user.id))
        assert response.status == "document_preparation_queued"
        assert response.can_cancel and response.model is None
        cancel_response = asyncio.run(UnifiedAssistantService(db).ask(
            request=request.model_copy(update={
                "question": "Druga oczekująca analiza dokumentu",
                "attempt_id": "isolated_cancel_20260826",
            }),
            user_id=user.id,
        ))
        cancelled = asyncio.run(UnifiedAssistantService(db).cancel(
            request_id=cancel_response.request_id, user_id=user.id
        ))
        assert cancelled.status == "cancelled"

        claimed = DocumentPreparationService(db).claim_next(); db.commit()
        assert claimed == same.id
        DocumentPreparationService(db).process_claimed(claimed)
        db.expire_all()
        ready = db.get(DocumentPreparationJob, claimed)
        assert ready.status == "running" and ready.stage == "local_analysis"
        intelligence = DocumentIntelligenceService(db)
        build_input = intelligence.collect_input(
            document_id=stored.document.id, preparation_job_id=claimed
        )
        source_ref = build_input.evidence[0].source_ref
        artifact = intelligence.persist(
            build_input=build_input,
            kind="baseline_document",
            artifact_key="default",
            payload={
                "document_class": "synthetic",
                "language": "pl",
                "summary": "Syntetyczny materiał testowy.",
                "topics": ["test"],
                "findings": [{
                    "kind": "fact",
                    "text": "Materiał zawiera syntetyczny dowód techniczny.",
                    "source_refs": [source_ref],
                }],
                "limitations": [],
            },
        )
        DocumentPreparationService(db).complete_intelligence(claimed, artifact.id)
        db.commit()
        db.expire_all()
        ready = db.get(DocumentPreparationJob, claimed)
        assert ready.status == "ready" and ready.stage == "ready_for_ai"
        assert db.query(DocumentPreparationJob).filter_by(document_id=stored.document.id).count() == 1

        async def accepted(*_args, **_kwargs):
            return UnifiedAssistantResponse(
                request_id="00000000-0000-0000-0000-000000000001",
                answer="Bezpieczna odpowiedź syntetyczna.", status="accepted_local",
                progress="complete", target_scope="TARGET_01", claims=[], sources=[],
                used_tools=[], model="synthetic", current_stage="complete",
            )

        waiting_id = _next_waiting_id()
        assert waiting_id == response.request_id
        with patch.object(UnifiedAssistantService, "ask", new=accepted):
            asyncio.run(resume_waiting_analysis(waiting_id))
        completed = asyncio.run(UnifiedAssistantService(db).status(request_id=waiting_id, user_id=user.id))
        assert completed.status == "accepted_local" and completed.answer

        # The V2 owner-failure class returns immediately, waits durably for one
        # exact historical material generation, then resumes without another
        # client request after the accepted artifact is available.
        v2_stored = DocumentService(db).store_document(
            content=b"synthetic two page soil report evidence",
            original_filename="synthetic-soil-report.txt",
            content_type="text/plain",
            source_type="manual_upload",
            intake_metadata={"actor_user_id": user.id},
        )
        v2_created = AssistantRunService(db).create(
            request=AssistantRunCreateRequest(
                question="Znajdź ten raport gruntu i podaj wnioski.",
                document_id=v2_stored.document.id,
                attempt_id="assistant_v2_material_20260826",
            ),
            user_id=user.id,
        )
        assert v2_created.status == "queued"
        asyncio.run(_execute_run(v2_created.run_id))
        db.expire_all()
        v2_waiting = AssistantRunService(db).get(
            run_id=v2_created.run_id, user_id=user.id
        )
        assert v2_waiting.status == "waiting"
        assert v2_waiting.current_stage == "waiting_for_material"

        v2_job = db.query(DocumentPreparationJob).filter_by(
            document_id=v2_stored.document.id
        ).one()
        assert DocumentPreparationService(db).claim_next() == v2_job.id
        db.commit()
        DocumentPreparationService(db).process_claimed(v2_job.id)
        db.expire_all()
        v2_input = DocumentIntelligenceService(db).collect_input(
            document_id=v2_stored.document.id,
            preparation_job_id=v2_job.id,
        )
        v2_ref = v2_input.evidence[0].source_ref
        v2_artifact = DocumentIntelligenceService(db).persist(
            build_input=v2_input,
            kind="baseline_document",
            artifact_key="default",
            payload={
                "document_class": "soil_report",
                "language": "pl",
                "summary": "Syntetyczny raport gruntu.",
                "topics": ["grunt"],
                "findings": [{
                    "kind": "fact",
                    "text": "Materiał jest syntetycznym raportem gruntu.",
                    "source_refs": [v2_ref],
                }],
                "limitations": [],
            },
        )
        DocumentPreparationService(db).complete_intelligence(v2_job.id, v2_artifact.id)
        db.commit()
        with patch.object(UnifiedAssistantService, "ask", new=accepted):
            asyncio.run(_execute_run(v2_created.run_id))
        db.expire_all()
        v2_completed = AssistantRunService(db).get(
            run_id=v2_created.run_id, user_id=user.id
        )
        assert v2_completed.status == "completed"
        assert v2_completed.result is not None
        bound_materials = db.query(AssistantRunMaterial).filter_by(
            assistant_run_id=v2_created.run_id
        ).all()
        assert bound_materials
        assert all(row.source_ref.startswith("S") for row in bound_materials)

        print("DOCUMENT_PREPARATION_PIPELINE_ISOLATED=PASS")
        print("DOCUMENT_PREPARATION_GENERATIONS=1")
        print("ASSISTANT_V2_MATERIAL_WAIT_AUTO_RESUME=PASS")
        print("HISTORICAL_BACKFILL=0")
    finally:
        db.close()
        settings.data_dir = previous_data_dir
        settings.assistant_pipeline_v2_enabled = previous_v2
        isolated_storage.cleanup()


if __name__ == "__main__":
    if os.environ.get("RUN_DOCUMENT_PREPARATION_INTEGRATION") == "1":
        integration_main()
    else:
        unittest.main()
