from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "p2" / "p2-wireframe-gate.json"


class P2GateReportTests(unittest.TestCase):
    def test_committed_gate_is_complete_and_passed(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["integration_gate_candidate"], "pass")
        self.assertEqual(report["blocking_issues"], 0)
        self.assertEqual(report["authority_drift"], 0)
        self.assertEqual(report["non_deterministic_svg"], 0)
        self.assertEqual(report["unsafe_svg"], 0)
        self.assertEqual(report["unexpected_page_rebuild"], 0)
        self.assertEqual(report["budgets"]["automatic_wireframe_redesign_count"], 0)
        self.assertLessEqual(report["budgets"]["m5_observed_host_model_invocations"], report["budgets"]["m5_host_model_invocation_ceiling"])
        self.assertTrue(report["gates"]["frozen_cases"]["D03"]["revision_isolation"])
        self.assertTrue(report["gates"]["frozen_cases"]["D08"]["order_only_page_reuse"])
        self.assertEqual(report["gates"]["runtime_and_p2_tests"]["tests"], 99)
        self.assertEqual(report["review_run"]["live_host_model_invocations"], 0)
        self.assertEqual(report["review_run"]["planner_calls"], 0)
        self.assertEqual(report["review_run"]["reviewer_calls"], 0)
        self.assertIn("pending post-merge verification", report["next_phase"])


if __name__ == "__main__":
    unittest.main()
