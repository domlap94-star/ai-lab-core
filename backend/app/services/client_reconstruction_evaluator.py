from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.schemas.client_reconstruction import ValidatedClientReconstruction
from app.services.client_reconstruction_evidence_service import ClientReconstructionEvidenceService
from app.services.client_reconstruction_policy_service import ClientReconstructionPolicyService
from app.services.openai_client_reconstruction_service import OpenAIClientReconstructionService


class ClientReconstructionEvaluator:
    """Reusable read-only evaluator for historical and future source events."""

    def __init__(self, db: Session, model_client: OpenAIClientReconstructionService) -> None:
        self.evidence = ClientReconstructionEvidenceService(db)
        self.policy = ClientReconstructionPolicyService(db)
        self.model_client = model_client

    def evaluate_client(self, client_id: int) -> tuple[dict[str, Any], ValidatedClientReconstruction, dict[str, int]]:
        packet = self.evidence.build(client_id)
        proposal, usage = self.model_client.evaluate(packet)
        return packet, self.policy.validate(packet, proposal), usage
