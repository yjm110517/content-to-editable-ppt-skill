from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "p2" / "p2-markdown-wireframe-gate.json"


class P2MarkdownGateReportTests(unittest.TestCase):
    def test_committed_markdown_gate_is_complete_and_passed(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["integration_gate_candidate"], "pass")
        self.assertEqual(report["blocking_issues"], 0)
        self.assertEqual(report["authority_drift"], 0)
        self.assertEqual(report["missing_or_unknown_content_refs"], 0)
        self.assertEqual(report["formal_p2_svg_generation"], 0)
        self.assertEqual(report["automatic_redesign"], 0)
        self.assertEqual(report["specialist_agent_calls"], 0)
        self.assertEqual([item["case_id"] for item in report["cases"]], ["D03", "D05", "D08"])
        self.assertEqual([item["pages"] for item in report["cases"]], [3, 5, 8])
        self.assertEqual(report["recorded_d03_host_model_invocations"], 1)
        self.assertEqual(report["d03_host_call_evidence"]["status"], "pass")
        self.assertEqual(report["review_run"]["live_host_model_invocations"], 0)
        self.assertTrue(report["p0_baseline_unchanged"])


if __name__ == "__main__":
    unittest.main()
