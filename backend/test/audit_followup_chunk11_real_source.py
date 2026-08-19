"""Read-only validation of Matching V2 against recent real Gmail sources.

The script prints aggregate decisions only. It never persists a decision and
never emits message text, identity values or Client names.
"""

from datetime import datetime
from statistics import median
from time import perf_counter

from sqlalchemy import text

from app.database.session import SessionLocal
from app.models.candidate_source import CandidateSource
from app.models.client_candidate import ClientCandidate
from app.repositories.import_repository import ImportRepository
from app.schemas.import_ingest import (
    CandidateDataInput,
    CandidateSourceInput,
    ImportIngestRequest,
)
from app.services.email_client_matching_service import EmailClientMatchingService
from app.services.forward_source_ingestion_service import ForwardSourceIngestionService


PATCH_BOUNDARY = datetime.fromisoformat("2026-08-16T22:12:03+02:00")
MAX_RECORDS = 20


def main() -> None:
    db = SessionLocal()
    try:
        rows = (
            db.query(CandidateSource, ClientCandidate)
            .join(ClientCandidate, ClientCandidate.id == CandidateSource.candidate_id)
            .filter(
                CandidateSource.source_type == "gmail_message",
                CandidateSource.created_at >= PATCH_BOUNDARY,
                CandidateSource.deleted_at.is_(None),
                ClientCandidate.deleted_at.is_(None),
            )
            .order_by(CandidateSource.created_at.asc(), CandidateSource.id.asc())
            .limit(MAX_RECORDS)
            .all()
        )
        matcher = EmailClientMatchingService(ImportRepository(db))
        counts = {
            "confirmed": 0,
            "linked_review": 0,
            "unlinked_review": 0,
            "exact_conflict": 0,
        }
        decisions = {key: 0 for key in ("certain", "high", "ambiguous", "unresolved")}
        durations_ms: list[float] = []
        for source, candidate in rows:
            request = ImportIngestRequest(
                import_source_id=source.import_source_id,
                import_run_id=source.import_run_id,
                candidate=CandidateDataInput(
                    client_type=candidate.client_type,
                    name=candidate.name,
                    legal_name=candidate.legal_name,
                    tax_id=candidate.tax_id,
                    registration_number=candidate.registration_number,
                    industry_id=candidate.industry_id,
                    website=candidate.website,
                    primary_email=candidate.primary_email,
                    primary_phone=candidate.primary_phone,
                    street=candidate.street,
                    building_number=candidate.building_number,
                    unit_number=candidate.unit_number,
                    postal_code=candidate.postal_code,
                    city=candidate.city,
                    country_code=candidate.country_code,
                    notes=None,
                    confidence=candidate.confidence,
                ),
                source=CandidateSourceInput(
                    source_type="gmail_message",
                    external_id=source.external_id,
                    external_parent_id=source.external_parent_id,
                    source_label=source.source_label,
                    source_url=source.source_url,
                    extracted_text=source.extracted_text,
                    raw_payload=source.raw_payload,
                ),
            )
            prepared = ForwardSourceIngestionService().prepare(request)
            started = perf_counter()
            decision = matcher.match(prepared)
            durations_ms.append((perf_counter() - started) * 1000)
            decisions[decision.confidence] += 1
            current = candidate.matched_client_id
            if current is None:
                counts["unlinked_review"] += 1
            elif (
                decision.confidence == "certain"
                and decision.client is not None
                and decision.client.id == current
            ):
                counts["confirmed"] += 1
            elif (
                current in decision.candidate_client_ids
                and decision.confidence in {"high", "ambiguous"}
            ):
                counts["linked_review"] += 1
            elif (
                decision.confidence == "certain"
                and decision.client is not None
                and decision.client.id != current
            ):
                counts["exact_conflict"] += 1
            else:
                counts["linked_review"] += 1

        print(f"records_sampled={len(rows)}")
        for key, value in counts.items():
            print(f"{key}={value}")
        for key, value in decisions.items():
            print(f"decision_{key}={value}")
        if durations_ms:
            print(f"matching_median_ms={median(durations_ms):.3f}")
            print(f"matching_max_ms={max(durations_ms):.3f}")
        v2_sources = sum(
            1
            for (payload,) in db.query(CandidateSource.raw_payload).all()
            if isinstance(payload, dict)
            and "_next_stabil_email_client_match_v2" in payload
        )
        ungranted_locks = db.execute(
            text("SELECT count(*) FROM pg_locks WHERE NOT granted")
        ).scalar_one()
        print(f"persisted_v2_sources={v2_sources}")
        print(f"ungranted_locks={ungranted_locks}")
        print("production_links_changed=0")
    finally:
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
