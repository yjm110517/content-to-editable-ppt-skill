from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "p3" / "p3-icon-resolution-gate.json"


class IconResolutionGateTests(unittest.TestCase):
    def test_committed_gate_closes_resolution_and_consumption(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["phase"], "P3.1-icon-resolution")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocking_issues"], 0)
        self.assertEqual(report["primary_library"], "tabler-icons")
        self.assertEqual(report["online_resolution_calls"], 0)
        self.assertEqual(report["independent_agent_calls"], 0)
        self.assertEqual(report["generative_icon_substitution"], 0)
        self.assertTrue(report["source_hashes_equal"])
        self.assertEqual(report["synthetic_preview"]["sanitized_svg_sha256"], report["ppt_runtime"]["builder_source_svg_sha256"])
        self.assertEqual(report["synthetic_preview"]["resvg_version"], "2.6.2")
        self.assertEqual([item["case_id"] for item in report["cases"]], ["D03", "D05", "D08"])
        self.assertTrue(all(item["icon_placeholders"] >= 1 and item["resolver_calls"] == 1 for item in report["cases"]))
        self.assertEqual(report["fallback_routes"]["raster_handoff"]["false_svg_success_artifacts"], 0)
        self.assertEqual(report["review_run"], {"live_host_model_invocations": 0, "planner_calls": 0, "reviewer_calls": 0, "icon_reviewer_calls": 0, "image_generation_calls": 0})


if __name__ == "__main__":
    unittest.main()
