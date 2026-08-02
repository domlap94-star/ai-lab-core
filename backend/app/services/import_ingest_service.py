from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.import_run import ImportRun
from app.models.import_source import ImportSource
from app.repositories.import_repository import ImportRepository
from app.schemas.import_ingest import (
    CandidateDataInput,
    CandidateSourceInput,
    ImportIngestRequest,
    ImportIngestResponse,
)


class ImportSourceNotFoundError(Exception):
    pass


class ImportSourceDisabledError(Exception):
    pass


class ImportRunNotFoundError(Exception):
    pass


class ImportRunSourceMismatchError(Exception):
    pass


@dataclass(frozen=True)
class CandidateMatch:
    candidate: ClientCandidate | None
    matched_client: Client | None
    matched_by: str | None


class ImportIngestService:
    def __init__(self, db: Session) -> None:
        self.repository = ImportRepository(db)

    def ingest(
        self,
        request: ImportIngestRequest,
    ) -> ImportIngestResponse:
        import_source = self._require_import_source(
            request.import_source_id,
        )

        import_run = self._resolve_import_run(
            run_id=request.import_run_id,
            import_source=import_source,
        )

        existing_source = self.repository.find_candidate_source(
            import_source_id=import_source.id,
            source_type=request.source.source_type,
            external_id=request.source.external_id,
        )

        if existing_source is not None:
            return ImportIngestResponse(
                candidate_id=existing_source.candidate_id,
                candidate_status=self._get_candidate_status(
                    existing_source.candidate_id,
                ),
                source_id=existing_source.id,
                created_candidate=False,
                created_source=False,
                matched_by="existing_source",
                matched_client_id=None,
            )

        try:
            if import_run is not None:
                self.repository.increment_import_run_counters(
                    import_run,
                    received=1,
                )

            match = self._find_match(request.candidate)

            created_candidate = False

            if match.candidate is not None:
                candidate = self._merge_candidate_data(
                    match.candidate,
                    request.candidate,
                )
                self.repository.update_candidate(candidate)

            else:
                candidate = self._create_candidate(
                    request=request,
                    matched_client=match.matched_client,
                )
                created_candidate = True

            candidate_source = self._create_candidate_source(
                candidate=candidate,
                import_source=import_source,
                import_run=import_run,
                source=request.source,
            )

            if import_run is not None:
                self.repository.increment_import_run_counters(
                    import_run,
                    processed=1,
                    candidates_created=1 if created_candidate else 0,
                    duplicates_detected=(
                        1 if match.matched_client is not None else 0
                    ),
                )

            import_source.status = "active"
            import_source.last_error = None

            self.repository.commit()

            return ImportIngestResponse(
                candidate_id=candidate.id,
                candidate_status=candidate.status,
                source_id=candidate_source.id,
                created_candidate=created_candidate,
                created_source=True,
                matched_by=match.matched_by,
                matched_client_id=(
                    match.matched_client.id
                    if match.matched_client is not None
                    else candidate.matched_client_id
                ),
            )

        except Exception:
            self.repository.rollback()
            raise

    def _require_import_source(
        self,
        source_id: int,
    ) -> ImportSource:
        source = self.repository.get_import_source(source_id)

        if source is None:
            raise ImportSourceNotFoundError

        if not source.is_enabled:
            raise ImportSourceDisabledError

        return source

    def _resolve_import_run(
        self,
        *,
        run_id: int | None,
        import_source: ImportSource,
    ) -> ImportRun | None:
        if run_id is None:
            return None

        import_run = self.repository.get_import_run(run_id)

        if import_run is None:
            raise ImportRunNotFoundError

        if import_run.source_id != import_source.id:
            raise ImportRunSourceMismatchError

        return import_run

    def _find_match(
        self,
        data: CandidateDataInput,
    ) -> CandidateMatch:
        if data.tax_id:
            client = self.repository.find_client_by_tax_id(
                data.tax_id,
            )

            if client is not None:
                candidate = self.repository.find_candidate_by_tax_id(
                    data.tax_id,
                )

                return CandidateMatch(
                    candidate=candidate,
                    matched_client=client,
                    matched_by="tax_id",
                )

            candidate = self.repository.find_candidate_by_tax_id(
                data.tax_id,
            )

            if candidate is not None:
                return CandidateMatch(
                    candidate=candidate,
                    matched_client=None,
                    matched_by="candidate_tax_id",
                )

        if data.primary_email:
            client = self.repository.find_client_by_email(
                data.primary_email,
            )

            if client is not None:
                candidate = self.repository.find_candidate_by_email(
                    data.primary_email,
                )

                return CandidateMatch(
                    candidate=candidate,
                    matched_client=client,
                    matched_by="email",
                )

            candidate = self.repository.find_candidate_by_email(
                data.primary_email,
            )

            if candidate is not None:
                return CandidateMatch(
                    candidate=candidate,
                    matched_client=None,
                    matched_by="candidate_email",
                )

        return CandidateMatch(
            candidate=None,
            matched_client=None,
            matched_by=None,
        )

    def _create_candidate(
        self,
        *,
        request: ImportIngestRequest,
        matched_client: Client | None,
    ) -> ClientCandidate:
        data = request.candidate

        candidate = ClientCandidate(
            import_run_id=request.import_run_id,
            client_type=data.client_type,
            name=self._resolve_candidate_name(data),
            legal_name=data.legal_name,
            tax_id=data.tax_id,
            registration_number=data.registration_number,
            industry_id=data.industry_id,
            website=data.website,
            primary_email=data.primary_email,
            primary_phone=data.primary_phone,
            street=data.street,
            building_number=data.building_number,
            unit_number=data.unit_number,
            postal_code=data.postal_code,
            city=data.city,
            country_code=data.country_code,
            notes=data.notes,
            status=(
                "duplicate"
                if matched_client is not None
                else "pending"
            ),
            confidence=data.confidence,
            matched_client_id=(
                matched_client.id
                if matched_client is not None
                else None
            ),
            source_summary=self._build_source_summary(
                request.source,
            ),
            raw_payload={
                "candidate": data.model_dump(),
                "source": request.source.model_dump(),
            },
        )

        return self.repository.create_candidate(candidate)

    def _merge_candidate_data(
        self,
        candidate: ClientCandidate,
        data: CandidateDataInput,
    ) -> ClientCandidate:
        candidate.client_type = self._prefer_value(
            candidate.client_type,
            data.client_type,
            empty_values={"other", ""},
        )

        candidate.name = self._prefer_value(
            candidate.name,
            self._resolve_candidate_name(data),
            empty_values={"", "Nieznany klient"},
        )

        candidate.legal_name = self._prefer_nullable(
            candidate.legal_name,
            data.legal_name,
        )
        candidate.tax_id = self._prefer_nullable(
            candidate.tax_id,
            data.tax_id,
        )
        candidate.registration_number = self._prefer_nullable(
            candidate.registration_number,
            data.registration_number,
        )
        candidate.industry_id = (
            candidate.industry_id
            if candidate.industry_id is not None
            else data.industry_id
        )
        candidate.website = self._prefer_nullable(
            candidate.website,
            data.website,
        )
        candidate.primary_email = self._prefer_nullable(
            candidate.primary_email,
            data.primary_email,
        )
        candidate.primary_phone = self._prefer_nullable(
            candidate.primary_phone,
            data.primary_phone,
        )
        candidate.street = self._prefer_nullable(
            candidate.street,
            data.street,
        )
        candidate.building_number = self._prefer_nullable(
            candidate.building_number,
            data.building_number,
        )
        candidate.unit_number = self._prefer_nullable(
            candidate.unit_number,
            data.unit_number,
        )
        candidate.postal_code = self._prefer_nullable(
            candidate.postal_code,
            data.postal_code,
        )
        candidate.city = self._prefer_nullable(
            candidate.city,
            data.city,
        )
        candidate.country_code = self._prefer_value(
            candidate.country_code,
            data.country_code,
            empty_values={"", "PL"},
        )
        candidate.notes = self._merge_notes(
            candidate.notes,
            data.notes,
        )
        candidate.confidence = max(
            candidate.confidence,
            data.confidence,
        )

        return candidate

    def _create_candidate_source(
        self,
        *,
        candidate: ClientCandidate,
        import_source: ImportSource,
        import_run: ImportRun | None,
        source: CandidateSourceInput,
    ) -> CandidateSource:
        candidate_source = CandidateSource(
            candidate_id=candidate.id,
            import_source_id=import_source.id,
            import_run_id=(
                import_run.id
                if import_run is not None
                else None
            ),
            source_type=source.source_type,
            external_id=source.external_id,
            external_parent_id=source.external_parent_id,
            source_label=source.source_label,
            source_url=source.source_url,
            extracted_text=source.extracted_text,
            raw_payload=source.raw_payload,
        )

        return self.repository.create_candidate_source(
            candidate_source,
        )

    def _get_candidate_status(
        self,
        candidate_id: int,
    ) -> str:
        candidate = (
            self.repository.db.query(ClientCandidate)
            .filter(ClientCandidate.id == candidate_id)
            .first()
        )

        return candidate.status if candidate is not None else "unknown"

    @staticmethod
    def _resolve_candidate_name(
        data: CandidateDataInput,
    ) -> str:
        for value in (
            data.name,
            data.legal_name,
            data.primary_email,
            data.website,
            data.primary_phone,
        ):
            if value:
                return value

        return "Nieznany klient"

    @staticmethod
    def _build_source_summary(
        source: CandidateSourceInput,
    ) -> str:
        values = [
            source.source_type,
            source.source_label,
            source.external_id,
        ]

        return " | ".join(
            value
            for value in values
            if value
        )

    @staticmethod
    def _prefer_nullable(
        current: str | None,
        incoming: str | None,
    ) -> str | None:
        if current and current.strip():
            return current

        return incoming

    @staticmethod
    def _prefer_value(
        current: str,
        incoming: str,
        *,
        empty_values: set[str],
    ) -> str:
        if current not in empty_values:
            return current

        return incoming

    @staticmethod
    def _merge_notes(
        current: str | None,
        incoming: str | None,
    ) -> str | None:
        if not incoming:
            return current

        if not current:
            return incoming

        if incoming in current:
            return current

        return f"{current}\n\n{incoming}"