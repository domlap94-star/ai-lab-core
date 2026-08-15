from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace

from app.services.client_candidate_promotion_service import (
    CandidatePromotionError,
    ClientCandidatePromotionService,
)
from app.services.client_entity_semantic_projection_service import (
    ClientEntitySemanticProjectionService,
)
from app.services.client_identity_name_quality_service import (
    ClientIdentityNameQualityService,
)
from app.services.client_identity_cleanup_dry_run_service import (
    CandidateCleanupProjection,
    CleanupEvidence,
    ClientIdentityCleanupDryRunService,
)


class EmptyQuery:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return []


class EmptySession:
    def query(self, *args, **kwargs):
        return EmptyQuery()


def candidate(**overrides):
    values = {
        "id": 1,
        "status": "pending",
        "matched_client_id": None,
        "name": "Jan Kowalski",
        "client_type": "person",
        "primary_email": "external@example.com",
        "primary_phone": None,
        "tax_id": None,
        "country_code": "PL",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def expect_promotion_rejected(item, phrase: str) -> None:
    try:
        ClientCandidatePromotionService._validate_candidate(item)
    except CandidatePromotionError as exc:
        assert phrase in str(exc)
    else:
        raise AssertionError("Suspicious candidate promotion was accepted")


def cleanup_projection(
    service,
    *,
    candidate_id: int,
    proposed_name: str,
    proposed_type: str,
    evidence: list[CleanupEvidence],
) -> CandidateCleanupProjection:
    support = service._identity_support_evidence(proposed_name, evidence)
    return CandidateCleanupProjection(
        candidate_id=candidate_id,
        candidate_status="accepted",
        proposed_name=proposed_name,
        proposed_client_type=proposed_type,
        legal_name=(proposed_name if proposed_type == "company" else None),
        contact_name=None,
        contact_email=None,
        contact_phone=None,
        tax_id=None,
        status="review",
        reason="Synthetic attribution control.",
        identity_confidence=max(
            (item.confidence for item in support),
            default=0.0,
        ),
        evidence=evidence,
        identity_support_evidence=support,
    )


def verify_identity_evidence_attribution() -> None:
    service = ClientIdentityCleanupDryRunService.__new__(
        ClientIdentityCleanupDryRunService
    )
    service.quality = ClientIdentityNameQualityService
    indexes = {
        key: defaultdict(set) for key in ("name", "tax", "email", "phone")
    }

    organization = "Example Construction Sp. z o.o."
    contact = "Jan Kowalski"
    organization_evidence = CleanupEvidence(
        candidate_id=1,
        source_id=10,
        source_type="gmail_message",
        method="signature_legal_entity",
        value=organization,
        confidence=0.88,
    )
    unrelated_contact = CleanupEvidence(
        candidate_id=1,
        source_id=10,
        source_type="gmail_message",
        method="semantic_contact",
        value=contact,
        confidence=0.95,
    )
    substring_evidence = CleanupEvidence(
        candidate_id=1,
        source_id=11,
        source_type="gmail_message",
        method="semantic_contact",
        value="Example Construction",
        confidence=0.99,
    )
    organization_projection = cleanup_projection(
        service,
        candidate_id=1,
        proposed_name=organization,
        proposed_type="company",
        evidence=[organization_evidence, unrelated_contact, substring_evidence],
    )
    assert organization_projection.identity_confidence == 0.88
    assert organization_projection.identity_support_evidence == [
        organization_evidence
    ]

    candidate_one = candidate(
        id=1,
        name="org@example.com",
        status="accepted",
        matched_client_id=100,
    )
    service._project_candidate = lambda item, source_types: organization_projection
    organization_proposal = service._build_proposal(
        client=SimpleNamespace(
            id=100,
            name="org@example.com",
            client_type="other",
            legal_name=None,
            tax_id=None,
            primary_email=None,
            primary_phone=None,
        ),
        candidates=[candidate_one],
        source_types={},
        document_counts={},
        duplicate_indexes=indexes,
    )
    assert organization_proposal.action == "REVIEW_REQUIRED"
    assert organization_proposal.confidence == 0.88
    assert unrelated_contact not in organization_proposal.identity_support_evidence
    assert substring_evidence not in organization_proposal.identity_support_evidence

    person_evidence = CleanupEvidence(
        candidate_id=2,
        source_id=20,
        source_type="google_sheets_row",
        method="person_contact_fallback",
        value=contact,
        confidence=0.95,
    )
    person_projection = cleanup_projection(
        service,
        candidate_id=2,
        proposed_name=contact,
        proposed_type="person",
        evidence=[person_evidence],
    )
    candidate_two = candidate(
        id=2,
        name="500 600 700",
        status="accepted",
        matched_client_id=101,
    )
    service._project_candidate = lambda item, source_types: person_projection
    person_proposal = service._build_proposal(
        client=SimpleNamespace(
            id=101,
            name="500 600 700",
            client_type="other",
            legal_name=None,
            tax_id=None,
            primary_email=None,
            primary_phone=None,
        ),
        candidates=[candidate_two],
        source_types={},
        document_counts={},
        duplicate_indexes=indexes,
    )
    assert person_proposal.action == "SAFE_RENAME_CANDIDATE"
    assert person_proposal.confidence == 0.95
    assert person_proposal.identity_support_evidence == [person_evidence]


def main() -> None:
    quality = ClientIdentityNameQualityService
    assert quality.suspicion_types("name@example.com") == ("EMAIL_AS_NAME",)
    assert quality.suspicion_types("+48 500-600-700") == ("PHONE_AS_NAME",)
    assert quality.suspicion_types("Oferta.pdf") == ("FILE_AS_NAME",)
    assert not quality.is_suspicious("Jan Kowalski")
    assert not quality.is_suspicious("ACME Sp. z o.o.")

    expect_promotion_rejected(candidate(name="name@example.com"), "EMAIL_AS_NAME")
    expect_promotion_rejected(candidate(name="500 600 700"), "PHONE_AS_NAME")
    expect_promotion_rejected(candidate(name="Oferta.pdf"), "FILE_AS_NAME")
    expect_promotion_rejected(
        candidate(primary_email="kontakt@podnoszenieposadzek.pl"),
        "first-party internal",
    )

    ClientCandidatePromotionService._validate_candidate(candidate())
    ClientCandidatePromotionService._validate_candidate(
        candidate(name="ACME Sp. z o.o.", client_type="company")
    )
    ClientCandidatePromotionService._validate_projection_status("review")
    try:
        ClientCandidatePromotionService._validate_projection_status(
            "relay_container"
        )
    except CandidatePromotionError:
        pass
    else:
        raise AssertionError("Relay container promotion was accepted")

    suspicious = candidate(
        name="name@example.com",
        status="accepted",
        matched_client_id=10,
    )
    projection = ClientEntitySemanticProjectionService(EmptySession()).project(
        suspicious,
        include_candidate_name_evidence=False,
    )
    assert projection.entity_name is None
    assert projection.status == "insufficient"
    assert not projection.entity_evidence

    normal = candidate(status="accepted", matched_client_id=10)
    legacy_projection = ClientEntitySemanticProjectionService(EmptySession()).project(
        normal
    )
    assert legacy_projection.entity_name == "Jan Kowalski"
    assert legacy_projection.entity_type == "person"

    verify_identity_evidence_attribution()

    print("CLIENT IDENTITY CLEANUP DRY-RUN REGRESSION: OK")


if __name__ == "__main__":
    main()
