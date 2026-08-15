from __future__ import annotations

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

    print("CLIENT IDENTITY CLEANUP DRY-RUN REGRESSION: OK")


if __name__ == "__main__":
    main()
