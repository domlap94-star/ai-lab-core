from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

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
    ImportBatchItemError,
    ImportBatchRequest,
    ImportBatchResponse,
    ImportIngestRequest,
    ImportIngestResponse,
)
from app.services.forward_client_contact_service import (
    ForwardClientContactService,
)
from app.services.forward_source_ingestion_service import (
    ForwardSourceIngestionService,
)
from app.services.ignored_mail_source_service import IgnoredMailSourceService
from app.services.email_client_matching_service import (
    EMAIL_MATCH_METADATA_KEY,
    EmailClientMatch,
    EmailClientMatchingService,
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


@dataclass(frozen=True)
class EmailCandidateResolutionPreview:
    """Read-only projection of the exact Gmail Candidate resolution path."""

    request: ImportIngestRequest
    email_match: EmailClientMatch
    match: CandidateMatch
    classification: str
    existing_candidate_id: int | None
    existing_client_id: int | None
    resolved_client_id: int | None
    expected_candidate_delta: int
    expected_new_client_link_delta: int
    ignored_unresolved: bool = False

    def signature(self) -> tuple[object, ...]:
        return (
            self.request.source.external_id,
            self.classification,
            self.existing_candidate_id,
            self.existing_client_id,
            self.resolved_client_id,
            self.expected_candidate_delta,
            self.expected_new_client_link_delta,
            self.ignored_unresolved,
        )


class ImportIngestService:
    _SHEETS_TRANSPORT_METADATA_KEYS = frozenset(
        {
            "next_stabil_forward_contacts_v1",
            "execution_id",
            "executionid",
            "execution_timestamp",
            "fetched_at",
            "fetchedat",
            "import_run_id",
            "run_id",
            "workflow_execution_id",
        }
    )

    def __init__(self, db: Session) -> None:
        self.repository = ImportRepository(db)
        self.forward_normalizer = ForwardSourceIngestionService()
        self.email_matching = EmailClientMatchingService(self.repository)

    def preview_email_resolution(
        self,
        request: ImportIngestRequest,
    ) -> EmailCandidateResolutionPreview:
        """Resolve a Gmail Candidate without mutating ORM or database state."""
        if request.source.source_type != "gmail_message":
            raise ValueError("email_resolution_requires_gmail_message")
        prepared = self.forward_normalizer.prepare(request)
        email_match = self.email_matching.match(prepared)
        match = self._find_candidate_for_email(
            prepared.candidate,
            email_match,
        )
        candidate = match.candidate
        if candidate is None:
            classification = "new_candidate"
        elif candidate.matched_client_id is None:
            classification = "reuse_existing_candidate_unlinked"
        else:
            classification = "reuse_existing_candidate_client_linked"
        creates_client_link = bool(
            match.matched_client is not None
            and (candidate is None or candidate.matched_client_id is None)
        )
        ignored_unresolved = bool(
            match.matched_client is None
            and IgnoredMailSourceService(self.repository.db).matches(
                prepared.candidate.primary_email
            )
        )
        return EmailCandidateResolutionPreview(
            request=prepared,
            email_match=email_match,
            match=match,
            classification=classification,
            existing_candidate_id=(candidate.id if candidate is not None else None),
            existing_client_id=(
                candidate.matched_client_id
                if candidate is not None
                else None
            ),
            resolved_client_id=(
                match.matched_client.id
                if match.matched_client is not None
                else None
            ),
            expected_candidate_delta=int(candidate is None),
            expected_new_client_link_delta=int(creates_client_link),
            ignored_unresolved=ignored_unresolved,
        )

    def ingest(
        self,
        request: ImportIngestRequest,
        *,
        email_resolution: EmailCandidateResolutionPreview | None = None,
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
            if request.source.source_type == "google_sheets_row":
                return self._update_existing_google_sheets_source(
                    existing_source=existing_source,
                    request=request,
                    import_source=import_source,
                    import_run=import_run,
                )

            candidate = self.repository.get_candidate(
                existing_source.candidate_id
            )
            metadata = self._existing_email_match_metadata(existing_source)
            return ImportIngestResponse(
                candidate_id=existing_source.candidate_id,
                candidate_status=self._get_candidate_status(
                    existing_source.candidate_id,
                ),
                source_id=existing_source.id,
                created_candidate=False,
                created_source=False,
                matched_by="existing_source",
                matched_client_id=(
                    candidate.matched_client_id if candidate is not None else None
                ),
                match_confidence=metadata.get("confidence"),
                match_reasons=list(metadata.get("reasons", [])),
                candidate_client_ids=list(
                    metadata.get("candidate_client_ids", [])
                ),
            )

        try:
            if import_run is not None:
                self.repository.increment_import_run_counters(
                    import_run,
                    received=1,
                )

            email_match: EmailClientMatch | None = None
            if request.source.source_type == "gmail_message":
                resolution = email_resolution or self.preview_email_resolution(
                    request
                )
                if (
                    resolution.request.source.external_id
                    != request.source.external_id
                ):
                    raise ValueError("email_resolution_source_mismatch")
                request = resolution.request
                email_match = resolution.email_match
                payload = dict(request.source.raw_payload or {})
                payload[EMAIL_MATCH_METADATA_KEY] = email_match.metadata()
                if resolution.ignored_unresolved:
                    payload["next_stabil_ignored_sender_v1"] = {
                        "ignored": True,
                    }
                request = request.model_copy(
                    update={
                        "source": request.source.model_copy(
                            update={"raw_payload": payload}
                        )
                    }
                )
                match = resolution.match
            else:
                # Forward-only boundary: existing historical CandidateSource
                # rows are never reinterpreted by this normalization layer.
                request = self.forward_normalizer.prepare(request)
                match = self._find_match(request.candidate)

            created_candidate = False

            if match.candidate is not None:
                candidate = self._merge_candidate_data(
                    match.candidate,
                    request.candidate,
                )

                if match.matched_client is not None:
                    candidate.status = "duplicate"
                    candidate.matched_client_id = match.matched_client.id

                self.repository.update_candidate(candidate)

            else:
                candidate = self._create_candidate(
                    request=request,
                    matched_client=match.matched_client,
                    ignored_unresolved=(
                        resolution.ignored_unresolved
                        if request.source.source_type == "gmail_message"
                        else False
                    ),
                )
                created_candidate = True

            candidate_source = self._create_candidate_source(
                candidate=candidate,
                import_source=import_source,
                import_run=import_run,
                source=request.source,
            )

            if match.matched_client is not None:
                ForwardClientContactService.add_from_payloads(
                    match.matched_client,
                    [request.source.raw_payload],
                    source_id=candidate_source.id,
                    source_type=candidate_source.source_type,
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
                match_confidence=(
                    email_match.confidence if email_match is not None else None
                ),
                match_reasons=(
                    list(email_match.reasons) if email_match is not None else []
                ),
                candidate_client_ids=(
                    list(email_match.candidate_client_ids)
                    if email_match is not None
                    else []
                ),
            )

        except Exception:
            self.repository.rollback()
            raise

    def _update_existing_google_sheets_source(
        self,
        *,
        existing_source: CandidateSource,
        request: ImportIngestRequest,
        import_source: ImportSource,
        import_run: ImportRun | None,
    ) -> ImportIngestResponse:
        try:
            if import_run is not None:
                self.repository.increment_import_run_counters(
                    import_run,
                    received=1,
                )

            candidate = self.repository.get_candidate(
                existing_source.candidate_id,
            )

            if candidate is None:
                raise ValueError(
                    "Candidate linked to the existing Google Sheets "
                    f"source {existing_source.id} was not found."
                )

            source_changed = self._source_has_changed(
                existing_source,
                request.source,
            )

            if not source_changed:
                if import_run is not None:
                    self.repository.increment_import_run_counters(
                        import_run,
                        processed=1,
                    )

                import_source.status = "active"
                import_source.last_error = None
                self.repository.commit()

                return ImportIngestResponse(
                    candidate_id=candidate.id,
                    candidate_status=candidate.status,
                    source_id=existing_source.id,
                    created_candidate=False,
                    created_source=False,
                    matched_by="existing_source",
                    matched_client_id=candidate.matched_client_id,
                )

            candidate_changed = self._candidate_has_sheet_changes(
                candidate,
                request.candidate,
            )

            if source_changed:
                self._apply_source_update(
                    existing_source,
                    request.source,
                    import_run,
                )

                self.repository.update_candidate_source(
                    existing_source,
                )

            if candidate_changed:
                self._merge_google_sheets_candidate_data(
                    candidate,
                    request.candidate,
                )

                candidate.source_summary = self._build_source_summary(
                    request.source,
                )

                candidate.raw_payload = {
                    "candidate": request.candidate.model_dump(),
                    "source": request.source.model_dump(),
                }

                self.repository.update_candidate(candidate)

            if import_run is not None:
                self.repository.increment_import_run_counters(
                    import_run,
                    processed=1,
                )

            import_source.status = "active"
            import_source.last_error = None

            self.repository.commit()

            return ImportIngestResponse(
                candidate_id=candidate.id,
                candidate_status=candidate.status,
                source_id=existing_source.id,
                created_candidate=False,
                created_source=False,
                matched_by=(
                    "existing_source_updated"
                    if source_changed or candidate_changed
                    else "existing_source"
                ),
                matched_client_id=candidate.matched_client_id,
            )

        except Exception:
            self.repository.rollback()
            raise

    def ingest_batch(
        self,
        request: ImportBatchRequest,
    ) -> ImportBatchResponse:
        results: list[ImportIngestResponse] = []
        errors: list[ImportBatchItemError] = []

        candidates_created = 0
        sources_created = 0
        existing_sources = 0
        duplicates_detected = 0

        for index, record in enumerate(request.records):
            try:
                result = self.ingest(record)

                results.append(result)

                if result.created_candidate:
                    candidates_created += 1

                if result.created_source:
                    sources_created += 1
                else:
                    existing_sources += 1

                if result.matched_client_id is not None:
                    duplicates_detected += 1

            except Exception as error:
                errors.append(
                    ImportBatchItemError(
                        index=index,
                        external_id=record.source.external_id,
                        error=(
                            str(error)
                            if str(error)
                            else error.__class__.__name__
                        ),
                    )
                )

        return ImportBatchResponse(
            received=len(request.records),
            processed=len(results),
            candidates_created=candidates_created,
            sources_created=sources_created,
            existing_sources=existing_sources,
            duplicates_detected=duplicates_detected,
            failed=len(errors),
            results=results,
            errors=errors,
        )

    def _require_import_source(
        self,
        source_id: int,
    ) -> ImportSource:
        source = self.repository.get_import_source(source_id)

        if source is None:
            raise ImportSourceNotFoundError(
                f"Import source {source_id} not found."
            )

        if not source.is_enabled:
            raise ImportSourceDisabledError(
                f"Import source {source_id} is disabled."
            )

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
            raise ImportRunNotFoundError(
                f"Import run {run_id} not found."
            )

        if import_run.source_id != import_source.id:
            raise ImportRunSourceMismatchError(
                "Import run does not belong to the selected source."
            )

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

        if data.primary_phone:
            client = self.repository.find_client_by_phone(data.primary_phone)
            if client is not None:
                candidate = self.repository.find_candidate_by_phone(
                    data.primary_phone
                )
                return CandidateMatch(
                    candidate=candidate,
                    matched_client=client,
                    matched_by="phone",
                )
            candidate = self.repository.find_candidate_by_phone(
                data.primary_phone
            )
            if candidate is not None:
                return CandidateMatch(
                    candidate=candidate,
                    matched_client=None,
                    matched_by="candidate_phone",
                )

        return CandidateMatch(
            candidate=None,
            matched_client=None,
            matched_by=None,
        )

    def _find_candidate_for_email(
        self,
        data: CandidateDataInput,
        decision: EmailClientMatch,
    ) -> CandidateMatch:
        matched_client = (
            decision.client if decision.confidence == "certain" else None
        )
        if matched_client is None:
            # Keep each uncertain future Gmail message independently
            # reviewable. Replays are still deduplicated by CandidateSource.
            return CandidateMatch(
                candidate=None,
                matched_client=None,
                matched_by=f"email_match_{decision.confidence}",
            )
        candidate: ClientCandidate | None = None
        # Reuse a prior pending/duplicate Candidate only when it cannot cross
        # an existing Client assignment. Source-id idempotency is handled
        # before this method and remains the primary replay guard.
        for finder, value in (
            (self.repository.find_candidate_by_tax_id, data.tax_id),
            (self.repository.find_candidate_by_email, data.primary_email),
            (self.repository.find_candidate_by_phone, data.primary_phone),
        ):
            if not value:
                continue
            found = finder(value)
            if found is None:
                continue
            target_id = matched_client.id if matched_client is not None else None
            if found.matched_client_id in {None, target_id}:
                candidate = found
                break

        return CandidateMatch(
            candidate=candidate,
            matched_client=matched_client,
            matched_by=(
                decision.reasons[0]
                if decision.confidence == "certain" and decision.reasons
                else f"email_match_{decision.confidence}"
            ),
        )

    @staticmethod
    def _existing_email_match_metadata(
        source: CandidateSource,
    ) -> dict[str, Any]:
        payload = source.raw_payload if isinstance(source.raw_payload, dict) else {}
        metadata = payload.get(EMAIL_MATCH_METADATA_KEY)
        return metadata if isinstance(metadata, dict) else {}

    def _create_candidate(
        self,
        *,
        request: ImportIngestRequest,
        matched_client: Client | None,
        ignored_unresolved: bool = False,
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
                "duplicate" if matched_client is not None else
                "rejected" if ignored_unresolved else "pending"
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

    def _merge_google_sheets_candidate_data(
        self,
        candidate: ClientCandidate,
        data: CandidateDataInput,
    ) -> ClientCandidate:
        if data.client_type and data.client_type != "other":
            candidate.client_type = data.client_type

        resolved_name = self._resolve_candidate_name(data)

        if self._should_replace_candidate_name(
            candidate.name,
            resolved_name,
        ):
            candidate.name = resolved_name

        self._set_if_present(
            candidate,
            "legal_name",
            data.legal_name,
        )
        self._set_if_present(
            candidate,
            "tax_id",
            data.tax_id,
        )
        self._set_if_present(
            candidate,
            "registration_number",
            data.registration_number,
        )

        if data.industry_id is not None:
            candidate.industry_id = data.industry_id

        self._set_if_present(
            candidate,
            "website",
            data.website,
        )
        self._set_if_present(
            candidate,
            "primary_email",
            data.primary_email,
        )
        self._set_if_present(
            candidate,
            "primary_phone",
            data.primary_phone,
        )
        self._set_if_present(
            candidate,
            "street",
            data.street,
        )
        self._set_if_present(
            candidate,
            "building_number",
            data.building_number,
        )
        self._set_if_present(
            candidate,
            "unit_number",
            data.unit_number,
        )
        self._set_if_present(
            candidate,
            "postal_code",
            data.postal_code,
        )
        self._set_if_present(
            candidate,
            "city",
            data.city,
        )

        if data.country_code:
            candidate.country_code = data.country_code

        if data.notes:
            candidate.notes = data.notes

        candidate.confidence = max(
            candidate.confidence,
            data.confidence,
        )

        return candidate

    def _candidate_has_sheet_changes(
        self,
        candidate: ClientCandidate,
        data: CandidateDataInput,
    ) -> bool:
        comparisons = (
            (
                candidate.client_type,
                data.client_type
                if data.client_type != "other"
                else None,
            ),
            (
                candidate.legal_name,
                data.legal_name,
            ),
            (
                candidate.tax_id,
                data.tax_id,
            ),
            (
                candidate.registration_number,
                data.registration_number,
            ),
            (
                candidate.industry_id,
                data.industry_id,
            ),
            (
                candidate.website,
                data.website,
            ),
            (
                candidate.primary_email,
                data.primary_email,
            ),
            (
                candidate.primary_phone,
                data.primary_phone,
            ),
            (
                candidate.street,
                data.street,
            ),
            (
                candidate.building_number,
                data.building_number,
            ),
            (
                candidate.unit_number,
                data.unit_number,
            ),
            (
                candidate.postal_code,
                data.postal_code,
            ),
            (
                candidate.city,
                data.city,
            ),
            (
                candidate.country_code,
                data.country_code,
            ),
            (
                candidate.notes,
                data.notes,
            ),
        )

        for current, incoming in comparisons:
            if incoming is None:
                continue

            if incoming == "Nieznany klient":
                continue

            if current != incoming:
                return True

        resolved_name = self._resolve_candidate_name(
            data
        )

        if self._should_replace_candidate_name(
            candidate.name,
            resolved_name,
        ):
            return True

        return False

    @classmethod
    def _should_replace_candidate_name(
        cls,
        current: str | None,
        incoming: str | None,
    ) -> bool:
        current_clean = cls._clean_candidate_name(
            current
        )

        incoming_clean = cls._clean_candidate_name(
            incoming
        )

        if not incoming_clean:
            return False

        if (
            incoming_clean.casefold()
            == "nieznany klient"
        ):
            return False

        if (
            current_clean.casefold()
            == incoming_clean.casefold()
        ):
            return False

        return (
            cls._candidate_name_quality(
                incoming_clean
            )
            >
            cls._candidate_name_quality(
                current_clean
            )
        )

    @staticmethod
    def _clean_candidate_name(
        value: str | None,
    ) -> str:
        if not value:
            return ""

        return " ".join(
            value.strip().split()
        )

    @classmethod
    def _candidate_name_quality(
        cls,
        value: str | None,
    ) -> int:
        text = cls._clean_candidate_name(
            value
        )

        if not text:
            return 0

        lowered = text.casefold()

        if lowered == "nieznany klient":
            return 0

        if "@" in text:
            return 0

        if (
            lowered.startswith("http://")
            or lowered.startswith("https://")
            or lowered.startswith("www.")
        ):
            return 0

        digits = "".join(
            character
            for character in text
            if character.isdigit()
        )

        non_digits = "".join(
            character
            for character in text
            if not character.isdigit()
        ).strip(" +-()/.")

        if (
            len(digits) >= 7
            and not non_digits
        ):
            return 0

        padded = f" {lowered} "

        address_markers = (
            " ul. ",
            " aleja ",
            " al. ",
            " os. ",
            " woj. ",
        )

        if any(
            marker in padded
            for marker in address_markers
        ):
            return 0

        if (
            "," in text
            and any(
                character.isdigit()
                for character in text
            )
        ):
            return 0

        tokens = [
            token
            for token in text.split()
            if token
        ]

        if len(tokens) >= 2:
            return 2

        return 1

    @classmethod
    def _source_has_changed(
        cls,
        existing_source: CandidateSource,
        incoming_source: CandidateSourceInput,
    ) -> bool:
        return cls._google_sheets_business_projection(
            existing_source
        ) != cls._google_sheets_business_projection(
            incoming_source
        )

    @classmethod
    def _google_sheets_business_projection(
        cls,
        source: CandidateSource | CandidateSourceInput,
    ) -> dict[str, Any]:
        """Return stable source-owned data used for Sheets idempotency."""
        return {
            "external_parent_id": cls._canonicalize_sheet_value(
                source.external_parent_id,
                field_name="external_parent_id",
            ),
            "source_label": cls._canonicalize_sheet_value(
                source.source_label,
                field_name="source_label",
            ),
            "source_url": cls._canonicalize_sheet_value(
                source.source_url,
                field_name="source_url",
            ),
            "extracted_text": cls._canonicalize_sheet_value(
                source.extracted_text,
                field_name="extracted_text",
            ),
            "raw_payload": cls._canonicalize_sheet_value(
                source.raw_payload,
                field_name="raw_payload",
            ),
        }

    @classmethod
    def _canonicalize_sheet_value(
        cls,
        value: Any,
        *,
        field_name: str | None = None,
    ) -> Any:
        normalized_key = cls._canonical_sheet_key(field_name)

        if value is None:
            return None

        if isinstance(value, str):
            normalized = " ".join(value.replace("\xa0", " ").split())
            if not normalized:
                return None

            if cls._is_email_field(normalized_key):
                emails = cls._canonical_contact_values(
                    ForwardSourceIngestionService.parse_emails(normalized).values
                )
                return emails or normalized.casefold()

            if cls._is_phone_field(normalized_key):
                phones = ForwardSourceIngestionService.parse_phones(normalized)
                if phones.values and not phones.ambiguous:
                    return cls._canonical_contact_values(phones.values)

            if cls._is_date_field(normalized_key):
                return cls._canonicalize_sheet_date(normalized)

            return normalized

        if isinstance(value, Mapping):
            result: dict[str, Any] = {}
            for key in sorted(value, key=lambda item: str(item).casefold()):
                normalized_child_key = cls._canonical_sheet_key(str(key))
                if normalized_child_key in cls._SHEETS_TRANSPORT_METADATA_KEYS:
                    continue
                canonical_value = cls._canonicalize_sheet_value(
                    value[key],
                    field_name=str(key),
                )
                if canonical_value is not None:
                    result[str(key)] = canonical_value
            return result

        if isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            canonical_items = [
                cls._canonicalize_sheet_value(item, field_name=field_name)
                for item in value
            ]
            canonical_items = [
                item
                for item in canonical_items
                if item is not None
            ]
            return sorted(canonical_items, key=repr)

        return value

    @staticmethod
    def _canonical_contact_values(values: Sequence[str]) -> tuple[str, ...]:
        return tuple(sorted(set(values)))

    @staticmethod
    def _canonical_sheet_key(value: str | None) -> str:
        if not value:
            return ""
        return re.sub(
            r"[^a-z0-9ąćęłńóśźż]+",
            "_",
            value.casefold(),
        ).strip("_")

    @staticmethod
    def _is_email_field(field_name: str) -> bool:
        tokens = set(field_name.split("_"))
        return "email" in tokens or "mail" in tokens

    @staticmethod
    def _is_phone_field(field_name: str) -> bool:
        tokens = set(field_name.split("_"))
        return bool(tokens.intersection({"phone", "telefon", "tel"}))

    @staticmethod
    def _is_date_field(field_name: str) -> bool:
        tokens = set(field_name.split("_"))
        return bool(tokens.intersection({"date", "data", "timestamp"}))

    @staticmethod
    def _canonicalize_sheet_date(value: str) -> str:
        for date_format in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, date_format).date().isoformat()
            except ValueError:
                continue

        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value

        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc)
        return parsed.isoformat()

    @staticmethod
    def _apply_source_update(
        existing_source: CandidateSource,
        incoming_source: CandidateSourceInput,
        import_run: ImportRun | None,
    ) -> None:
        existing_source.import_run_id = (
            import_run.id
            if import_run is not None
            else existing_source.import_run_id
        )

        existing_source.external_parent_id = (
            incoming_source.external_parent_id
        )
        existing_source.source_label = (
            incoming_source.source_label
        )
        existing_source.source_url = (
            incoming_source.source_url
        )
        existing_source.extracted_text = (
            incoming_source.extracted_text
        )
        existing_source.raw_payload = (
            incoming_source.raw_payload
        )

    @staticmethod
    def _set_if_present(
        candidate: ClientCandidate,
        attribute: str,
        value: object,
    ) -> None:
        if value is not None:
            setattr(
                candidate,
                attribute,
                value,
            )

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
        candidate = self.repository.get_candidate(
            candidate_id,
        )

        if candidate is None:
            return "unknown"

        return candidate.status

    @staticmethod
    def _resolve_candidate_name(
        data: CandidateDataInput,
    ) -> str:
        for value in (
            data.name,
            data.legal_name,
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
