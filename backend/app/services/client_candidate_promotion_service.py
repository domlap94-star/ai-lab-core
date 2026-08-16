from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.client_contact_point import ClientContactPoint
from app.models.candidate_source import CandidateSource
from app.models.document import Document
from app.services.forward_client_contact_service import (
    ForwardClientContactService,
)
from app.services.client_identity_name_quality_service import (
    ClientIdentityNameQualityService,
)
from app.services.client_entity_projection_policy_service import (
    ClientEntityProjectionPolicyService,
)
from app.services.first_party_identity_registry import (
    FirstPartyIdentityRegistry,
)


class CandidateNotFoundError(Exception):
    pass


class CandidateNotPendingError(Exception):
    pass


class CandidateAlreadyMatchedError(Exception):
    pass


class CandidateDuplicateClientError(Exception):
    def __init__(
        self,
        *,
        client_id: int,
        matched_by: str,
    ) -> None:
        self.client_id = client_id
        self.matched_by = matched_by

        super().__init__(
            "Candidate matches existing client "
            f"{client_id} by {matched_by}."
        )


class CandidatePromotionError(Exception):
    pass


class ClientCandidatePromotionService:
    CLIENT_FIELDS = (
        "client_type",
        "name",
        "legal_name",
        "tax_id",
        "registration_number",
        "industry_id",
        "website",
        "primary_email",
        "primary_phone",
        "street",
        "building_number",
        "unit_number",
        "postal_code",
        "city",
        "country_code",
        "notes",
    )

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def get_candidate_for_update(
        self,
        candidate_id: int,
    ) -> ClientCandidate:
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
            raise CandidateNotFoundError(
                f"Candidate {candidate_id} not found."
            )

        return candidate

    def find_existing_client(
        self,
        candidate: ClientCandidate,
    ) -> tuple[
        Client | None,
        str | None,
    ]:
        if candidate.tax_id:
            normalized_tax_id = self._normalize_identifier(
                candidate.tax_id
            )

            if normalized_tax_id:
                client = (
                    self.db.query(Client)
                    .filter(
                        Client.deleted_at.is_(None),
                        func.regexp_replace(
                            func.lower(Client.tax_id),
                            r"[^a-z0-9]",
                            "",
                            "g",
                        )
                        == normalized_tax_id,
                    )
                    .first()
                )

                if client is not None:
                    return client, "tax_id"

        if candidate.primary_email:
            normalized_email = (
                candidate.primary_email
                .strip()
                .lower()
            )

            client = (
                self.db.query(Client)
                .filter(
                    Client.deleted_at.is_(None),
                    or_(
                        func.lower(func.trim(Client.primary_email))
                        == normalized_email,
                        Client.contact_points.any(
                            and_(
                                ClientContactPoint.deleted_at.is_(None),
                                ClientContactPoint.kind == "email",
                                ClientContactPoint.normalized_value
                                == normalized_email,
                            )
                        ),
                    ),
                )
                .first()
            )

            if client is not None:
                return client, "email"

        if candidate.primary_phone:
            normalized_phone = self._normalize_phone(
                candidate.primary_phone
            )

            if normalized_phone:
                client = (
                    self.db.query(Client)
                    .filter(
                        Client.deleted_at.is_(None),
                        or_(
                            func.regexp_replace(
                                Client.primary_phone,
                                r"[^0-9]",
                                "",
                                "g",
                            ).in_((normalized_phone, f"48{normalized_phone}")),
                            Client.contact_points.any(
                                and_(
                                    ClientContactPoint.deleted_at.is_(None),
                                    ClientContactPoint.kind == "phone",
                                    ClientContactPoint.normalized_value.in_(
                                        (normalized_phone, f"48{normalized_phone}")
                                    ),
                                )
                            ),
                        ),
                    )
                    .first()
                )
                if client is not None:
                    return client, "phone"

        return None, None

    def promote(
        self,
        candidate_id: int,
    ) -> Client:
        candidate = self.get_candidate_for_update(
            candidate_id
        )

        self._validate_candidate(
            candidate
        )

        identity_projection = (
            ClientEntityProjectionPolicyService(self.db).project(candidate)
        )
        self._validate_projection_status(identity_projection.status)

        existing_client, matched_by = (
            self.find_existing_client(
                candidate
            )
        )

        if existing_client is not None:
            raise CandidateDuplicateClientError(
                client_id=existing_client.id,
                matched_by=(
                    matched_by
                    or "unknown"
                ),
            )

        client = Client(
            **{
                field_name: getattr(
                    candidate,
                    field_name,
                )
                for field_name
                in self.CLIENT_FIELDS
            }
        )

        self.db.add(
            client
        )

        self.db.flush()

        source_payloads = [
            source.raw_payload
            for source in (
                self.db.query(CandidateSource)
                .filter(
                    CandidateSource.candidate_id == candidate.id,
                    CandidateSource.deleted_at.is_(None),
                )
                .order_by(CandidateSource.id.asc())
                .all()
            )
        ]
        ForwardClientContactService.add_from_payloads(
            client,
            source_payloads,
        )

        candidate.status = "accepted"
        candidate.matched_client_id = client.id

        now = datetime.now(
            timezone.utc
        )

        documents = (
            self.db.query(Document)
            .filter(
                Document.candidate_id
                == candidate.id,
            )
            .all()
        )

        for document in documents:
            if (
                document.client_id
                is not None
                and document.client_id
                != client.id
            ):
                raise CandidatePromotionError(
                    "Document "
                    f"{document.id} is already "
                    f"assigned to client "
                    f"{document.client_id}."
                )

            document.client_id = (
                client.id
            )

            if document.match_status in (
                "unmatched",
                "suggested",
                "matched",
            ):
                document.match_status = (
                    "confirmed"
                )

            document.match_confidence = (
                1.0
            )

            document.match_method = (
                "candidate_accept"
            )

            document.matched_at = now

        self.db.flush()

        return client

    @staticmethod
    def _validate_candidate(
        candidate: ClientCandidate,
    ) -> None:
        if candidate.status != "pending":
            raise CandidateNotPendingError(
                "Candidate "
                f"{candidate.id} has status "
                f"{candidate.status!r}; "
                "expected 'pending'."
            )

        if (
            candidate.matched_client_id
            is not None
        ):
            raise CandidateAlreadyMatchedError(
                "Candidate "
                f"{candidate.id} is already matched "
                f"to client "
                f"{candidate.matched_client_id}."
            )

        if (
            not candidate.name
            or not candidate.name.strip()
        ):
            raise CandidatePromotionError(
                "Candidate "
                f"{candidate.id} has no usable name."
            )

        suspicion_types = (
            ClientIdentityNameQualityService.suspicion_types(
                candidate.name
            )
        )

        if suspicion_types:
            raise CandidatePromotionError(
                "Candidate "
                f"{candidate.id} has a suspicious identity name "
                f"({', '.join(suspicion_types)}); source-backed "
                "identity review is required before promotion."
            )

        additional_findings = (
            ClientIdentityNameQualityService.additional_findings(candidate.name)
        )
        if "ADDRESS_OR_LOCATION_AS_NAME" in additional_findings:
            raise CandidatePromotionError(
                "Candidate "
                f"{candidate.id} has an address/location as identity name; "
                "source-backed identity review is required before promotion."
            )

        if FirstPartyIdentityRegistry.is_first_party_email(
            candidate.primary_email
        ):
            raise CandidatePromotionError(
                "Candidate "
                f"{candidate.id} is a first-party internal identity "
                "and cannot be promoted to a CRM client."
            )

        if candidate.client_type not in (
            "company",
            "person",
            "institution",
            "other",
        ):
            raise CandidatePromotionError(
                "Candidate "
                f"{candidate.id} has invalid "
                f"client_type "
                f"{candidate.client_type!r}."
            )

        if (
            not candidate.country_code
            or len(candidate.country_code.strip()) != 2
        ):
            raise CandidatePromotionError(
                "Candidate "
                f"{candidate.id} has invalid "
                f"country_code {candidate.country_code!r}."
            )

    @staticmethod
    def _validate_projection_status(status: str) -> None:
        if status in {"relay_container", "first_party_internal"}:
            raise CandidatePromotionError(
                "Candidate projection is a first-party or relay "
                "transport identity and cannot be promoted."
            )

    @staticmethod
    def _normalize_identifier(
        value: str | None,
    ) -> str:
        if not value:
            return ""

        return "".join(
            character.lower()
            for character
            in value.strip()
            if character.isalnum()
        )

    @staticmethod
    def _normalize_phone(
        value: str | None,
    ) -> str:
        if not value:
            return ""

        digits = re.sub(
            r"\D",
            "",
            value,
        )

        if digits.startswith("48") and len(digits) == 11:
            digits = digits[2:]

        return digits
