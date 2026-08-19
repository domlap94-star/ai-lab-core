from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.candidate_merge_event import CandidateMergeEvent
from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_address import ClientAddress
from app.models.client_candidate import ClientCandidate
from app.models.document import Document
from app.schemas.client_candidate_review import (
    CandidateDuplicateMatch as CandidateDuplicateMatchSchema,
    CandidateMergeAuditPayload,
    CandidateMergeFieldProposal,
    CandidateMergeIdentity,
    CandidateMergePreviewResponse,
    CandidateMergeRelationCounts,
    CandidateMergeRequest,
    CandidateMergeResponse,
)
from app.services.client_candidate_promotion_service import (
    ClientCandidatePromotionService,
)
from app.services.client_identity_name_quality_service import (
    ClientIdentityNameQualityService,
)
from app.services.client_workflow_status_projection_service import (
    ClientWorkflowStatusProjectionService,
)
from app.services.forward_client_contact_service import (
    ForwardClientContactService,
)
from app.services.forward_source_ingestion_service import CONTACT_METADATA_KEY


class CandidateMergeNotFoundError(Exception):
    pass


class CandidateMergeConflictError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class CandidateMergeValidationError(Exception):
    pass


@dataclass(frozen=True)
class _Proposal:
    field: str
    candidate_value: str | None
    target_value: str | None
    action: str
    required: bool


class CandidateMergeService:
    MAX_MATCHES = 10
    SCALAR_FIELDS = ("name", "legal_name", "tax_id")

    def __init__(self, db: Session) -> None:
        self.db = db
        self.matcher = ClientCandidatePromotionService(db)

    def preview(
        self,
        *,
        candidate_id: int,
        target_client_id: int,
    ) -> CandidateMergePreviewResponse:
        candidate = self._candidate(candidate_id)
        target, match = self._validated_target(candidate, target_client_id)
        proposals = self._proposals(candidate, target)
        counts = self._relation_counts(candidate, target)
        blocked = [
            f"{item.field}:manual_resolution_required"
            for item in proposals
            if item.required
        ]
        return CandidateMergePreviewResponse(
            candidate=self._candidate_identity(candidate),
            target=self._client_identity(target),
            match=self._match_schema(match),
            field_proposals=[
                CandidateMergeFieldProposal(
                    field=item.field,
                    candidate_value=item.candidate_value,
                    target_value=item.target_value,
                    proposed_action=item.action,
                    required_resolution=item.required,
                )
                for item in proposals
            ],
            relation_counts=counts.model_dump(),
            expected_candidate_version=self._version(candidate.updated_at),
            blocked_reasons=blocked,
        )

    def merge(
        self,
        *,
        candidate_id: int,
        actor_user_id: int,
        request: CandidateMergeRequest,
    ) -> CandidateMergeResponse:
        existing_event = (
            self.db.query(CandidateMergeEvent)
            .filter(CandidateMergeEvent.operation_id == request.operation_id)
            .first()
        )
        if existing_event is not None:
            if (
                existing_event.candidate_id != candidate_id
                or existing_event.target_client_id != request.target_client_id
            ):
                raise CandidateMergeConflictError(
                    "MERGE_OPERATION_CONFLICT",
                    "Operation ID belongs to a different merge.",
                )
            target = self._client(existing_event.target_client_id)
            return self._event_response(existing_event, target, replay=True)

        try:
            candidate = (
                self.db.query(ClientCandidate)
                .filter(
                    ClientCandidate.id == candidate_id,
                    ClientCandidate.deleted_at.is_(None),
                )
                .with_for_update()
                .first()
            )
            if candidate is None:
                raise CandidateMergeNotFoundError("Candidate not found.")

            if candidate.status == "merged":
                if candidate.matched_client_id != request.target_client_id:
                    raise CandidateMergeConflictError(
                        "CANDIDATE_ALREADY_MERGED",
                        "Candidate is already merged to another Client.",
                    )
                prior = (
                    self.db.query(CandidateMergeEvent)
                    .filter(
                        CandidateMergeEvent.candidate_id == candidate.id,
                        CandidateMergeEvent.target_client_id
                        == request.target_client_id,
                    )
                    .order_by(CandidateMergeEvent.id.desc())
                    .first()
                )
                if prior is None:
                    raise CandidateMergeConflictError(
                        "MERGE_AUDIT_MISSING",
                        "Candidate is merged but has no merge audit event.",
                    )
                return self._event_response(
                    prior, self._client(request.target_client_id), replay=True
                )

            if candidate.status not in {"pending", "duplicate"}:
                raise CandidateMergeConflictError(
                    "CANDIDATE_STATE_CONFLICT",
                    "Candidate state does not allow merge.",
                )
            if self._version(candidate.updated_at) != self._normalized_version(
                request.expected_candidate_version
            ):
                raise CandidateMergeConflictError(
                    "CANDIDATE_VERSION_CONFLICT",
                    "Candidate changed after merge preview.",
                )

            target, _ = self._validated_target(candidate, request.target_client_id)
            proposals = self._proposals(candidate, target)
            decisions = self._resolve_decisions(proposals, request.field_decisions)
            changed_fields: list[str] = []

            for field in self.SCALAR_FIELDS:
                if decisions[field] == "take_candidate":
                    value = getattr(candidate, field)
                    if getattr(target, field) != value:
                        setattr(target, field, value)
                        changed_fields.append(field)

            contacts_added = self._merge_contacts(candidate, target)
            if contacts_added:
                changed_fields.append("contacts")
            addresses_added = self._merge_address(
                candidate, target, decisions["address"]
            )
            if addresses_added:
                changed_fields.append("addresses")

            documents = (
                self.db.query(Document)
                .filter(Document.candidate_id == candidate.id)
                .with_for_update()
                .all()
            )
            documents_relinked = 0
            now = datetime.now(timezone.utc)
            for document in documents:
                if document.client_id not in (None, target.id):
                    raise CandidateMergeConflictError(
                        "DOCUMENT_CLIENT_CONFLICT",
                        "A Candidate Document belongs to another Client.",
                    )
                if document.client_id != target.id:
                    document.client_id = target.id
                    documents_relinked += 1
                document.match_status = "confirmed"
                document.match_confidence = 1.0
                document.match_method = "candidate_merge"
                document.matched_at = now
            if documents_relinked:
                changed_fields.append("documents")

            source_counts = self._source_counts(candidate.id)
            if source_counts["emails"]:
                changed_fields.append("emails")
            changed_fields.extend(["candidate_status", "matched_client_id"])
            changed_fields = list(dict.fromkeys(changed_fields))

            candidate.status = "merged"
            candidate.matched_client_id = target.id

            relation_counts = CandidateMergeRelationCounts(
                contacts_added=contacts_added,
                addresses_added=addresses_added,
                documents_relinked=documents_relinked,
                emails_relinked=source_counts["emails"],
                sources_preserved=source_counts["all"],
            )
            audit_payload = CandidateMergeAuditPayload(
                changed_fields=changed_fields,
                relation_counts=relation_counts,
            )
            event = CandidateMergeEvent(
                operation_id=request.operation_id,
                actor_user_id=actor_user_id,
                candidate_id=candidate.id,
                target_client_id=target.id,
                action="candidate_merged",
                changed_fields=audit_payload.changed_fields,
                relation_counts=audit_payload.relation_counts.model_dump(),
            )
            self.db.add(event)
            self.db.flush()
            self.db.commit()
            self.db.refresh(event)
            self.db.refresh(target)
            return self._event_response(event, target, replay=False)
        except Exception:
            self.db.rollback()
            raise

    def _candidate(self, candidate_id: int) -> ClientCandidate:
        candidate = (
            self.db.query(ClientCandidate)
            .filter(
                ClientCandidate.id == candidate_id,
                ClientCandidate.deleted_at.is_(None),
            )
            .first()
        )
        if candidate is None:
            raise CandidateMergeNotFoundError("Candidate not found.")
        if candidate.status not in {"pending", "duplicate"}:
            raise CandidateMergeConflictError(
                "CANDIDATE_STATE_CONFLICT",
                "Candidate state does not allow merge preview.",
            )
        return candidate

    def _client(self, client_id: int) -> Client:
        client = (
            self.db.query(Client)
            .filter(Client.id == client_id, Client.deleted_at.is_(None))
            .first()
        )
        if client is None:
            raise CandidateMergeNotFoundError("Target Client not found.")
        return client

    def _validated_target(self, candidate: ClientCandidate, target_id: int):
        matches = self.matcher.find_existing_clients(
            candidate, limit=self.MAX_MATCHES
        )
        match = next((item for item in matches if item.client.id == target_id), None)
        if match is None:
            raise CandidateMergeConflictError(
                "TARGET_NOT_DETERMINISTIC_MATCH",
                "Target Client is not a deterministic Candidate match.",
            )
        return match.client, match

    def _match_schema(self, match) -> CandidateDuplicateMatchSchema:
        projection = ClientWorkflowStatusProjectionService(self.db).get_for_client_ids(
            [match.client.id]
        )[match.client.id]
        return CandidateDuplicateMatchSchema(
            client_id=match.client.id,
            client_name=match.client.name,
            workflow_status=projection.status,
            workflow_status_label=projection.label,
            confidence="certain",
            reasons=list(match.reasons),
        )

    def duplicate_schemas(self, matches) -> list[dict]:
        return [self._match_schema(match).model_dump() for match in matches]

    def _candidate_identity(self, candidate: ClientCandidate) -> CandidateMergeIdentity:
        return CandidateMergeIdentity(
            id=candidate.id,
            name=candidate.name,
            legal_name=candidate.legal_name,
            tax_id=candidate.tax_id,
            emails=self._bounded([candidate.primary_email]),
            phones=self._bounded([candidate.primary_phone]),
            addresses=self._candidate_addresses(candidate),
        )

    def _client_identity(self, client: Client) -> CandidateMergeIdentity:
        projection = ClientWorkflowStatusProjectionService(self.db).get_for_client_ids(
            [client.id]
        )[client.id]
        return CandidateMergeIdentity(
            id=client.id,
            name=client.name,
            legal_name=client.legal_name,
            tax_id=client.tax_id,
            emails=self._bounded(
                [client.primary_email] + [item.value for item in client.emails]
            ),
            phones=self._bounded(
                [client.primary_phone] + [item.value for item in client.phones]
            ),
            addresses=[self._address_dict(item) for item in client.addresses[:20]],
            workflow_status=projection.status,
            workflow_status_label=projection.label,
        )

    def _proposals(self, candidate: ClientCandidate, target: Client) -> list[_Proposal]:
        result: list[_Proposal] = []
        for field in self.SCALAR_FIELDS:
            candidate_value = self._clean(getattr(candidate, field))
            target_value = self._clean(getattr(target, field))
            if not candidate_value or self._same_value(
                field, candidate_value, target_value
            ):
                action, required = "keep_existing", False
            elif not target_value:
                action, required = "take_candidate", False
            else:
                action, required = "manual_conflict", True
            result.append(_Proposal(field, candidate_value, target_value, action, required))
        for field in ("primary_email", "primary_phone"):
            candidate_value = self._clean(getattr(candidate, field))
            target_value = self._clean(getattr(target, field))
            action = (
                "add"
                if candidate_value
                and not self._same_value(field, candidate_value, target_value)
                else "keep_existing"
            )
            result.append(_Proposal(field, candidate_value, target_value, action, False))
        candidate_address = self._address_text(candidate)
        target_address = self._address_text(target)
        action = (
            "add"
            if candidate_address
            and self._normalized_address(candidate)
            not in {self._normalized_address(item) for item in target.addresses}
            else "keep_existing"
        )
        result.append(_Proposal("address", candidate_address, target_address, action, False))
        return result

    @staticmethod
    def _resolve_decisions(
        proposals: list[_Proposal], supplied: dict[str, str]
    ) -> dict[str, str]:
        decisions: dict[str, str] = {}
        for proposal in proposals:
            decision = supplied.get(proposal.field, proposal.action)
            if proposal.required and decision not in {
                "keep_existing",
                "take_candidate",
            }:
                raise CandidateMergeValidationError(
                    f"Field {proposal.field} requires an explicit decision."
                )
            if not proposal.required and decision != proposal.action:
                raise CandidateMergeValidationError(
                    f"Field {proposal.field} must use the previewed action."
                )
            if proposal.field in {"name", "legal_name", "tax_id"} and decision == "add":
                raise CandidateMergeValidationError(
                    f"Field {proposal.field} cannot use add."
                )
            decisions[proposal.field] = decision
        return decisions

    def _merge_contacts(self, candidate: ClientCandidate, target: Client) -> int:
        sources = (
            self.db.query(CandidateSource)
            .filter(
                CandidateSource.candidate_id == candidate.id,
                CandidateSource.deleted_at.is_(None),
            )
            .order_by(CandidateSource.id.asc())
            .all()
        )
        added = ForwardClientContactService.add_from_payloads(
            target,
            [
                {
                    CONTACT_METADATA_KEY: {
                        "emails": self._bounded([candidate.primary_email]),
                        "phones": self._bounded([candidate.primary_phone]),
                    }
                }
            ],
            source_type="other",
        )
        for source in sources:
            added += ForwardClientContactService.add_from_payloads(
                target,
                [source.raw_payload],
                source_id=source.id,
                source_type=source.source_type,
            )
        return added

    def _merge_address(
        self, candidate: ClientCandidate, target: Client, decision: str
    ) -> int:
        if decision != "add" or not self._address_text(candidate):
            return 0
        normalized = self._normalized_address(candidate)
        existing = {self._normalized_address(item) for item in target.addresses}
        if normalized in existing:
            return 0
        target.address_records.append(
            ClientAddress(
                label="Adres kandydata",
                street=candidate.street,
                building_number=candidate.building_number,
                unit_number=candidate.unit_number,
                postal_code=candidate.postal_code,
                city=candidate.city,
                country_code=candidate.country_code,
                is_primary=False,
                position=len(target.address_records),
                origin="other",
                source_type="candidate_merge",
            )
        )
        return 1

    def _relation_counts(
        self, candidate: ClientCandidate, target: Client
    ) -> CandidateMergeRelationCounts:
        sources = self._source_counts(candidate.id)
        return CandidateMergeRelationCounts(
            contacts_added=self._preview_contacts_added(candidate, target),
            addresses_added=(
                1
                if self._address_text(candidate)
                and self._normalized_address(candidate)
                not in {
                    self._normalized_address(item) for item in target.addresses
                }
                else 0
            ),
            documents_relinked=self.db.query(Document).filter(
                Document.candidate_id == candidate.id,
                Document.client_id.is_(None),
            ).count(),
            emails_relinked=sources["emails"],
            sources_preserved=sources["all"],
        )

    def _preview_contacts_added(
        self, candidate: ClientCandidate, target: Client
    ) -> int:
        incoming: list[tuple[str, str]] = []
        for kind, value in (
            ("email", candidate.primary_email),
            ("phone", candidate.primary_phone),
        ):
            if self._clean(value):
                incoming.append((kind, value))
        sources = self.db.query(CandidateSource).filter(
            CandidateSource.candidate_id == candidate.id,
            CandidateSource.deleted_at.is_(None),
        )
        for source in sources:
            metadata = (source.raw_payload or {}).get(CONTACT_METADATA_KEY)
            if not isinstance(metadata, dict):
                continue
            for kind, key in (("email", "emails"), ("phone", "phones")):
                values = metadata.get(key)
                if isinstance(values, list):
                    incoming.extend(
                        (kind, value) for value in values if isinstance(value, str)
                    )

        existing = {
            (item.kind, item.normalized_value)
            for item in target.contact_points
            if item.kind in {"email", "phone"}
        }
        for kind, value in (
            ("email", target.primary_email),
            ("phone", target.primary_phone),
        ):
            normalized = self._normalize_contact(kind, value)
            if normalized:
                existing.add((kind, normalized))
        additions: set[tuple[str, str]] = set()
        for kind, value in incoming:
            normalized = self._normalize_contact(kind, value)
            item = (kind, normalized)
            if normalized and item not in existing:
                additions.add(item)
        return len(additions)

    @staticmethod
    def _normalize_contact(kind: str, value: str | None) -> str:
        if kind == "email":
            return ClientIdentityNameQualityService.normalize_email(value)
        return ClientIdentityNameQualityService.normalize_phone(value)

    def _source_counts(self, candidate_id: int) -> dict[str, int]:
        sources = self.db.query(CandidateSource).filter(
            CandidateSource.candidate_id == candidate_id,
            CandidateSource.deleted_at.is_(None),
        )
        return {
            "all": sources.count(),
            "emails": sources.filter(
                CandidateSource.source_type.in_(("gmail_message", "gmail_thread"))
            ).count(),
        }

    @staticmethod
    def _event_response(
        event: CandidateMergeEvent, target: Client, *, replay: bool
    ) -> CandidateMergeResponse:
        return CandidateMergeResponse(
            operation_id=event.operation_id,
            candidate_id=event.candidate_id,
            candidate_status="merged",
            client_id=target.id,
            client_name=target.name,
            changed_fields=list(event.changed_fields),
            relation_counts=dict(event.relation_counts),
            idempotent_replay=replay,
        )

    @staticmethod
    def _version(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _normalized_version(value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _clean(value) -> str | None:
        text = " ".join(str(value or "").split())
        return text or None

    @staticmethod
    def _same_value(field: str, left: str, right: str | None) -> bool:
        if not right:
            return False
        if field == "tax_id":
            return ClientIdentityNameQualityService.normalize_tax_id(
                left
            ) == ClientIdentityNameQualityService.normalize_tax_id(right)
        if field == "primary_email":
            return ClientIdentityNameQualityService.normalize_email(
                left
            ) == ClientIdentityNameQualityService.normalize_email(right)
        if field == "primary_phone":
            return ClientIdentityNameQualityService.normalize_phone(
                left
            ) == ClientIdentityNameQualityService.normalize_phone(right)
        return left.casefold() == right.casefold()

    @classmethod
    def _bounded(cls, values) -> list[str]:
        return list(dict.fromkeys(cls._clean(value) for value in values if cls._clean(value)))[:20]

    @classmethod
    def _address_text(cls, value) -> str | None:
        parts = [
            value.street,
            value.building_number,
            value.unit_number,
            value.postal_code,
            value.city,
            value.country_code,
        ]
        return cls._clean(" ".join(str(item or "") for item in parts))

    @classmethod
    def _normalized_address(cls, value) -> str:
        return (cls._address_text(value) or "").casefold()

    @staticmethod
    def _candidate_addresses(candidate: ClientCandidate) -> list[dict]:
        if not CandidateMergeService._address_text(candidate):
            return []
        return [
            {
                "street": candidate.street,
                "building_number": candidate.building_number,
                "unit_number": candidate.unit_number,
                "postal_code": candidate.postal_code,
                "city": candidate.city,
                "country_code": candidate.country_code,
                "is_primary": False,
            }
        ]

    @staticmethod
    def _address_dict(address: ClientAddress) -> dict:
        return {
            "street": address.street,
            "building_number": address.building_number,
            "unit_number": address.unit_number,
            "postal_code": address.postal_code,
            "city": address.city,
            "country_code": address.country_code,
            "is_primary": address.is_primary,
        }
