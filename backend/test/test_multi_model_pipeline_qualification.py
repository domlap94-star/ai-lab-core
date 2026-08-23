import unittest
import json
from pathlib import Path

from multi_model_pipeline_cases import orchestration_cases
from run_multi_model_pipeline_qualification import (
    base_graph,
    deterministic_tool_results,
    deterministic_tools,
    run_orchestration_suite,
    validate_graph,
    validate_final_response,
    validate_plan,
)
from local_llm_qualification_cases import cases


class MultiModelPipelineQualificationTests(unittest.TestCase):
    def test_canonical_evidence_graph_is_source_bound(self) -> None:
        for case in cases():
            graph = base_graph(case)
            self.assertEqual(graph["request_id"], case.case_id)
            self.assertEqual(validate_graph(graph, case), [])
            self.assertTrue(all(fact["source_refs"] for fact in graph["facts"]))

    def test_deterministic_router_uses_only_allowed_tools(self) -> None:
        for case in cases():
            plan = {"tool_plan": deterministic_tools(case), "source_refs": list(case.evidence), "domains": [ref.split(":", 1)[0] for ref in case.evidence]}
            self.assertEqual(validate_plan(plan, case), [])

    def test_supplementary_orchestration_matrix(self) -> None:
        self.assertEqual(len(orchestration_cases()), 15)
        result = run_orchestration_suite()
        self.assertEqual(result["cases"], 15)
        self.assertEqual(result["passed"], 15)

    def test_canonical_calculator_result_is_source_bound(self) -> None:
        pressure = next(case for case in cases() if case.case_id == "T06-pressure")
        result = deterministic_tool_results(pressure)
        self.assertEqual(result[0]["value"], 3.0)
        self.assertEqual(result[0]["unit"], "MPa")
        self.assertEqual(set(result[0]["source_refs"]), set(pressure.evidence))

    def test_final_response_rejects_foreign_claim_source(self) -> None:
        case = cases()[0]
        response = {"used_sources": ["client:A"], "claims": [{"class": "FACT", "source_refs": ["client:B"]}]}
        self.assertIn("claim_source_scope_invalid", validate_final_response(response, case))

    def test_tracked_evidence_schema_has_all_handoff_sections(self) -> None:
        schema = json.loads((Path(__file__).parent / "fixtures" / "unified_evidence_artifact_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(set(schema["required"]), {
            "request_id", "scope", "facts", "estimates", "hypotheses", "missing",
            "contradictions", "tool_results", "visual_observations", "unresolved_questions",
        })


if __name__ == "__main__":
    unittest.main()
