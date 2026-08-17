"""Focused schema/service contracts that do not mutate the production DB."""

from datetime import date
from pathlib import Path

from app.schemas.client_bulk import ClientIdBatchRequest, ClientWorkflowBatchRequest
from app.schemas.client_candidate_review import CandidateBulkAcceptRequest
from app.services.client_source_record_date_service import ClientSourceRecordDateService


def main() -> None:
    assert ClientIdBatchRequest(client_ids=[1, 2]).client_ids == [1, 2]
    assert CandidateBulkAcceptRequest(candidate_ids=[3, 4]).candidate_ids == [3, 4]
    status = ClientWorkflowBatchRequest(
        client_ids=[1, 2], status="inspection", effective_date=date(2026, 8, 17)
    )
    assert status.effective_date == date(2026, 8, 17)
    assert ClientSourceRecordDateService.parse_value("01.08.2026") == date(2026, 8, 1)

    migration = Path("/app/alembic/versions/prechunk11status_20260817_add_client_workflow_status.py").read_text()
    upgrade = migration.split("def downgrade", 1)[0].upper()
    assert "DROP" not in upgrade
    assert 'ONDELETE="RESTRICT"' in upgrade
    assert "CLIENT_WORKFLOW_STATUSES" in upgrade
    assert "UPDATE CLIENTS" not in upgrade

    print("PRE-CHUNK 11 CRM CONTRACT TEST PASS")


if __name__ == "__main__":
    main()
