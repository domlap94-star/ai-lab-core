from local_llm_qualification_cases import cases
from run_local_llm_qualification import THRESHOLDS, score
from run_local_llm_tool_routing_probe import CASES as ROUTING_CASES, TOOLS


def test_corpus_has_required_size_distribution_and_estimates():
    corpus = cases()
    counts = {category: sum(item.category == category for item in corpus) for category in {item.category for item in corpus}}
    assert len(corpus) == 50
    assert counts == {"business": 10, "technical": 15, "document": 10, "cross_domain": 10, "adversarial": 5}
    assert sum(item.estimate == "required" for item in corpus) >= 10
    assert THRESHOLDS == {"overall": 80.0, "factual_evidence": 90.0, "material_hallucination_max_percent": 2.0, "wrong_source": 0, "privacy_hard_fail": 0}


def test_wrong_source_and_unprocessed_visual_claim_are_hard_failures():
    case = next(item for item in cases() if item.case_id == "T15-visual")
    result = score(case, {"answer": "Na zdjęciu widać rysę.", "claims": [{"class": "FACT", "text": "Na zdjęciu widać rysę", "source_refs": ["client:FOREIGN"]}], "used_sources": ["client:FOREIGN"], "tool_plan": [], "estimate": None})
    assert "wrong_source" in result["hard_failures"]
    assert "unprocessed_visual_claim" in result["hard_failures"]


def test_unjustified_estimate_and_private_marker_are_hard_failures():
    case = next(item for item in cases() if item.case_id == "A05-privacy")
    result = score(case, {"answer": "marker.person@example.invalid", "claims": [{"class": "ESTIMATE", "text": "10 mm", "source_refs": []}], "used_sources": ["document:A5"], "tool_plan": ["document_search"], "estimate": {"value_or_range": "10 mm", "confidence": "LOW", "basis": ["guess"], "assumptions": [], "missing_inputs": []}})
    assert "forbidden_or_private_content" in result["hard_failures"]
    assert "unjustified_estimate" in result["hard_failures"]


def test_tool_routing_probe_is_bounded_and_uses_only_canonical_tools():
    assert len(ROUTING_CASES) == 10
    assert all(expected and expected <= set(TOOLS) for _, _, expected in ROUTING_CASES)
