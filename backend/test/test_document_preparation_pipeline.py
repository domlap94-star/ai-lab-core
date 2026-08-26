from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from pathlib import Path

from app.database.session import SessionLocal
from app.models.document_preparation_job import DocumentPreparationJob
from app.models.role import Role
from app.models.user import User
from app.schemas.unified_assistant import UnifiedAssistantRequest, UnifiedAssistantResponse
from app.services.document_preparation_dispatcher import _next_waiting_id, resume_waiting_analysis
from app.services.document_file_safety_service import DocumentFileSafetyService
from app.services.document_preparation_service import DocumentPreparationService
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

        print("DOCUMENT_PREPARATION_PIPELINE_ISOLATED=PASS")
        print("DOCUMENT_PREPARATION_GENERATIONS=1")
        print("HISTORICAL_BACKFILL=0")
    finally:
        db.close()


if __name__ == "__main__":
    if os.environ.get("RUN_DOCUMENT_PREPARATION_INTEGRATION") == "1":
        integration_main()
    else:
        unittest.main()
