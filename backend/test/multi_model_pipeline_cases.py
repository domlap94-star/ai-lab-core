from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrchestrationCase:
    case_id: str
    scenario: str
    expected: str


def orchestration_cases() -> list[OrchestrationCase]:
    """Frozen fault-injection cases for the orchestration boundary."""
    result = [
        OrchestrationCase("O01", "document specialist preserves an in-scope source", "accept"),
        OrchestrationCase("O02", "specialist emits an unknown source", "reject"),
        OrchestrationCase("O03", "specialist emits a FACT without a source", "reject"),
        OrchestrationCase("O04", "specialist emits an unsupported statement", "reject"),
        OrchestrationCase("O05", "two supported claims contradict", "flag_contradiction"),
        OrchestrationCase("O06", "planner chooses the wrong domain", "repair_with_deterministic_router"),
        OrchestrationCase("O07", "planner invents a tool", "reject"),
        OrchestrationCase("O08", "specialist estimate has no basis", "reject"),
        OrchestrationCase("O09", "specialist estimate has bounded basis", "accept"),
        OrchestrationCase("O10", "cross-domain claims retain both sources", "accept"),
        OrchestrationCase("O11", "visual question has no visual result", "require_visual_route"),
        OrchestrationCase("O12", "visual observation has an allowed source", "accept"),
        OrchestrationCase("O13", "restricted material requests escalation", "block_escalation"),
        OrchestrationCase("O14", "hard public-safe case fails local quality", "require_temp_chat"),
        OrchestrationCase("O15", "easy grounded case passes local quality", "keep_local"),
    ]
    assert len(result) == 15
    return result
