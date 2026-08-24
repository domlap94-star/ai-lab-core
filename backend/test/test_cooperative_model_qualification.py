import json
import tempfile
import unittest
from pathlib import Path

from rebase_validated_specialist_results import load
from run_cooperative_model_validation import expected_reject


class CooperativeModelQualificationTests(unittest.TestCase):
    def test_expected_reject_enforces_hard_source_privacy_and_quality_gates(self) -> None:
        passing = {"score": {"overall": 95, "factual": 95, "evidence": 95, "privacy": True}}
        self.assertFalse(expected_reject(passing))
        for delta in (
            {"hard_failures": ["unsupported"]},
            {"foreign_sources": ["client:B"]},
            {"privacy": False},
            {"overall": 79},
            {"factual": 80},
        ):
            row = json.loads(json.dumps(passing))
            row["score"].update(delta)
            self.assertTrue(expected_reject(row), delta)

    def test_latest_jsonl_row_wins_for_bounded_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            path.write_text(
                json.dumps({"case_id": "T01", "error": "first"}) + "\n"
                + json.dumps({"case_id": "T01", "score": {"overall": 90}}) + "\n",
                encoding="utf-8",
            )
            self.assertNotIn("error", load(path)["T01"])


if __name__ == "__main__":
    unittest.main()
