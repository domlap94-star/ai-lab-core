from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from app.schemas.import_ingest import ImportIngestRequest
from app.services.import_ingest_service import ImportIngestService


class FakeImportRepository:
    def __init__(self, candidate) -> None:
        self.candidate = candidate
        self.source_updates = 0
        self.candidate_updates = 0
        self.commits = 0

    def get_candidate(self, candidate_id: int):
        assert candidate_id == self.candidate.id
        return self.candidate

    def update_candidate_source(self, source) -> None:
        self.source_updates += 1

    def update_candidate(self, candidate) -> None:
        self.candidate_updates += 1

    def increment_import_run_counters(self, *args, **kwargs) -> None:
        pass

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        raise AssertionError("The idempotency test path must not roll back")


def build_candidate():
    return SimpleNamespace(
        id=77,
        status="pending",
        matched_client_id=None,
        client_type="person",
        name="Stable Person",
        legal_name=None,
        tax_id=None,
        registration_number=None,
        industry_id=None,
        website=None,
        primary_email="stable@example.com",
        primary_phone="500600700",
        street=None,
        building_number=None,
        unit_number=None,
        postal_code=None,
        city=None,
        country_code="PL",
        notes="Candidate state belongs to another source",
        confidence=0.8,
        source_summary=None,
        raw_payload=None,
    )


def build_source(external_id: str, payload: dict):
    return SimpleNamespace(
        id=hash(external_id) % 100000 + 1,
        candidate_id=77,
        external_parent_id=None,
        source_label=f"Sheet row {external_id}",
        source_url=None,
        extracted_text=None,
        raw_payload=deepcopy(payload),
        import_run_id=None,
    )


def build_request(
    external_id: str,
    payload: dict,
    *,
    notes: str,
    phone: str = "500600700",
    email: str = "stable@example.com",
) -> ImportIngestRequest:
    return ImportIngestRequest.model_validate(
        {
            "import_source_id": 1,
            "candidate": {
                "client_type": "person",
                "name": "Stable Person",
                "primary_email": email,
                "primary_phone": phone,
                "country_code": "PL",
                "notes": notes,
                "confidence": 0.8,
            },
            "source": {
                "source_type": "google_sheets_row",
                "external_id": external_id,
                "source_label": f"Sheet row {external_id}",
                "raw_payload": deepcopy(payload),
            },
        }
    )


def build_service(candidate):
    service = object.__new__(ImportIngestService)
    service.repository = FakeImportRepository(candidate)
    return service


def ingest_existing(service, source, request):
    import_source = SimpleNamespace(id=1, status="active", last_error=None)
    return service._update_existing_google_sheets_source(
        existing_source=source,
        request=request,
        import_source=import_source,
        import_run=None,
    )


def verify_unchanged_single_source() -> None:
    candidate = build_candidate()
    service = build_service(candidate)
    payload = {"row_number": 1, "Notes": "Source A"}
    source = build_source("A", payload)
    request = build_request("A", payload, notes="Source A")

    service._candidate_has_sheet_changes = lambda *args: (_ for _ in ()).throw(
        AssertionError("candidate diff must be gated by source change")
    )
    response = ingest_existing(service, source, request)

    assert response.matched_by == "existing_source"
    assert service.repository.source_updates == 0
    assert service.repository.candidate_updates == 0


def verify_two_shared_candidate_sources() -> None:
    candidate = build_candidate()
    service = build_service(candidate)
    sources = [
        build_source("A", {"row_number": 1, "Notes": "Source A"}),
        build_source("B", {"row_number": 2, "Notes": "Source B"}),
    ]
    requests = [
        build_request("A", sources[0].raw_payload, notes="Source A"),
        build_request("B", sources[1].raw_payload, notes="Source B"),
    ]

    for _ in range(2):
        for source, request in zip(sources, requests, strict=True):
            response = ingest_existing(service, source, request)
            assert response.matched_by == "existing_source"

    assert service.repository.source_updates == 0
    assert service.repository.candidate_updates == 0


def verify_three_shared_candidate_sources() -> None:
    candidate = build_candidate()
    service = build_service(candidate)
    sources = [
        build_source("A", {"row_number": 1, "Notes": "Source A"}),
        build_source("B", {"row_number": 2, "Notes": "Source B"}),
        build_source("C", {"row_number": 3, "Notes": "Source C"}),
    ]
    requests = [
        build_request("A", sources[0].raw_payload, notes="Source A"),
        build_request("B", sources[1].raw_payload, notes="Source B"),
        build_request("C", sources[2].raw_payload, notes="Source C"),
    ]

    for _ in range(3):
        for source, request in zip(sources, requests, strict=True):
            assert ingest_existing(service, source, request).matched_by == "existing_source"

    assert service.repository.source_updates == 0
    assert service.repository.candidate_updates == 0


def verify_real_change_updates_once() -> None:
    candidate = build_candidate()
    service = build_service(candidate)
    source = build_source(
        "A",
        {"row_number": 1, "Phone": "500600700", "Notes": "Old"},
    )
    changed_payload = {
        "row_number": 1,
        "Phone": "+48 700 800 900",
        "Notes": "Changed",
    }
    changed = build_request(
        "A",
        changed_payload,
        notes="Changed",
        phone="700800900",
    )

    assert ingest_existing(service, source, changed).matched_by == "existing_source_updated"
    assert ingest_existing(service, source, changed).matched_by == "existing_source"
    assert ingest_existing(service, source, changed).matched_by == "existing_source"
    assert service.repository.source_updates == 1
    assert service.repository.candidate_updates == 1


def verify_canonical_projection() -> None:
    left = build_source(
        "A",
        {
            "Notes": None,
            "Optional": "   ",
            "Date": "2026-08-17",
            "Phone": "+48 500 600 700",
            "Email": "  Person@Example.COM ",
            "Tags": ["beta", "alpha"],
            "execution_id": "old-run",
        },
    )
    right = build_request(
        "A",
        {
            "Date": "17.08.2026",
            "Phone": "500600700",
            "Email": "person@example.com",
            "Tags": ["alpha", "beta"],
            "execution_id": "new-run",
        },
        notes="Any",
    ).source

    assert not ImportIngestService._source_has_changed(left, right)

    changed_phone = right.model_copy(
        update={
            "raw_payload": {
                **right.raw_payload,
                "Phone": "700800900",
            }
        }
    )
    assert ImportIngestService._source_has_changed(left, changed_phone)


def main() -> None:
    verify_unchanged_single_source()
    verify_two_shared_candidate_sources()
    verify_three_shared_candidate_sources()
    verify_real_change_updates_once()
    verify_canonical_projection()
    print("Google Sheets source idempotency tests: PASS")


if __name__ == "__main__":
    main()
