from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "p2" / "p2-visual-placeholder-gate.json"


class P2VisualPlaceholderGateTests(unittest.TestCase):
    def test_gate_records_p2_1_without_live_model_calls(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["phase"], "P2.1-visual-placeholder")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocking_issues"], 0)
        self.assertEqual(report["authority_drift"], 0)
        self.assertEqual(report["missing_or_unknown_content_refs"], 0)
        self.assertEqual(report["recorded_d03_host_model_invocations"], 0)
        self.assertEqual(report["review_run"]["live_host_model_invocations"], 0)
        self.assertEqual([item["case_id"] for item in report["cases"]], ["D03", "D05", "D08"])
        self.assertEqual([item["pages"] for item in report["cases"]], [3, 5, 8])


if __name__ == "__main__":
    unittest.main()
