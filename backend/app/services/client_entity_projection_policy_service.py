from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.client_candidate import ClientCandidate
from app.services.client_entity_projection_service import (
    ClientEntityProjection,
    ClientEntityProjectionService,
)
from app.services.first_party_identity_registry import (
    FirstPartyIdentityRegistry,
)


class ClientEntityProjectionPolicyService:
    """
    Client Entity Projection Policy 1.3.1.

    READ ONLY.

    Adds first-party isolation and relay-container preservation
    on top of ClientEntityProjectionService.

    Separation of responsibilities:

        GmailMessageBoundaryService
            -> current-author vs quoted content

        FirstPartyIdentityRegistry
            -> identities belonging to our organization

        ClientEntityProjectionService
            -> semantic entity/contact projection

        ClientEntityProjectionPolicyService
            -> prevents first-party identities from becoming
               CRM clients and preserves technical relay
               containers regardless of transport ownership

    No database writes.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

        self.projection_service = (
            ClientEntityProjectionService(
                db
            )
        )

        self.registry = (
            FirstPartyIdentityRegistry
        )

    def project(
        self,
        candidate: ClientCandidate,
        *,
        include_candidate_name_evidence: bool = True,
    ) -> ClientEntityProjection:
        projection = (
            self.projection_service.project(
                candidate,
                include_candidate_name_evidence=(
                    include_candidate_name_evidence
                ),
            )
        )

        return self._apply_policy(
            candidate=candidate,
            projection=projection,
        )

    def _apply_policy(
        self,
        *,
        candidate: ClientCandidate,
        projection: ClientEntityProjection,
    ) -> ClientEntityProjection:
        candidate_is_first_party = (
            self.registry
            .is_first_party_email(
                candidate.primary_email
            )
        )

        # ====================================================
        # FIRST-PARTY TECHNICAL MAILBOX
        # ====================================================

        if candidate_is_first_party:
            if (
                projection.gmail_relay_messages
                > 0
            ):
                self._make_relay_container(
                    projection,
                    reason=(
                        "First-party mailbox contains "
                        "explicit contact-form relay messages. "
                        "The mailbox itself must not become "
                        "a CRM client."
                    ),
                )

                return projection

            self._make_first_party_internal(
                projection
            )

            return projection

        # ====================================================
        # EXTERNAL CANDIDATE:
        # REMOVE FIRST-PARTY LEAKAGE
        # ====================================================

        projection.evidence = [
            item
            for item in projection.evidence
            if not self._is_first_party_evidence(
                item.value
            )
        ]

        if (
            projection.tax_id
            and self.registry
            .is_first_party_tax_id(
                projection.tax_id
            )
        ):
            projection.tax_id = None

        if (
            projection.contact_name
            and self.registry
            .is_first_party_person(
                projection.contact_name
            )
        ):
            projection.contact_name = None

        if (
            projection.entity_name
            and self.registry
            .is_first_party_entity(
                projection.entity_name
            )
        ):
            projection.entity_name = None
            projection.entity_type = "other"
            projection.legal_name = None

        if (
            projection.contact_email
            and self.registry
            .is_first_party_email(
                projection.contact_email
            )
        ):
            projection.contact_email = None

        # ====================================================
        # EXTERNAL / THIRD-PARTY RELAY TRANSPORT
        # ====================================================
        #
        # A relay container does not have to use one of our
        # own mailboxes. SaaS / transactional systems can be
        # third-party transport addresses.
        #
        # If explicit relay messages exist and no genuine
        # client entity/contact survives, preserve the record
        # as a relay container rather than downgrading it to
        # generic "insufficient".
        # ====================================================

        if (
            projection.gmail_relay_messages
            > 0
            and projection.entity_name is None
            and projection.contact_name is None
        ):
            self._make_relay_container(
                projection,
                reason=(
                    "Candidate is a technical transport "
                    "container for explicit contact-form "
                    "relay messages and does not represent "
                    "a single CRM client."
                ),
            )

            return projection

        # ====================================================
        # EXTERNAL PERSON FALLBACK
        # ====================================================

        if projection.entity_name is None:
            if (
                projection.contact_name
                and not self.registry
                .is_first_party_person(
                    projection.contact_name
                )
            ):
                projection.entity_name = (
                    projection.contact_name
                )

                projection.entity_type = (
                    "person"
                )

        if projection.entity_name is None:
            projection.status = (
                "insufficient"
            )

            projection.reason = (
                "No external client identity remains "
                "after first-party isolation."
            )

        return projection

    # ========================================================
    # POLICY STATES
    # ========================================================

    @staticmethod
    def _make_relay_container(
        projection: ClientEntityProjection,
        *,
        reason: str,
    ) -> None:
        projection.entity_name = None
        projection.entity_type = "other"

        projection.legal_name = None

        projection.contact_name = None
        projection.contact_email = None
        projection.contact_phone = None

        projection.organizational_unit = None
        projection.tax_id = None

        projection.status = (
            "relay_container"
        )

        projection.reason = reason

        # Evidence collected for the transport identity must
        # not be exposed as CRM client identity evidence.
        #
        # Raw CandidateSource provenance remains untouched in DB.
        projection.evidence = []

    @staticmethod
    def _make_first_party_internal(
        projection: ClientEntityProjection,
    ) -> None:
        projection.entity_name = None
        projection.entity_type = "other"

        projection.legal_name = None

        projection.contact_name = None
        projection.contact_email = None
        projection.contact_phone = None

        projection.organizational_unit = None
        projection.tax_id = None

        projection.status = (
            "first_party_internal"
        )

        projection.reason = (
            "Candidate primary email belongs to "
            "the first-party organization and must "
            "not be projected as a CRM client."
        )

        projection.evidence = []

    # ========================================================
    # HELPERS
    # ========================================================

    @classmethod
    def _is_first_party_evidence(
        cls,
        value: str | None,
    ) -> bool:
        if not value:
            return False

        registry = (
            FirstPartyIdentityRegistry
        )

        return (
            registry.is_first_party_tax_id(
                value
            )
            or registry.is_first_party_person(
                value
            )
            or registry.is_first_party_entity(
                value
            )
            or registry.is_first_party_email(
                value
            )
        )
