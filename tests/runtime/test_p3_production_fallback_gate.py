from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "p3" / "p3-production-fallback-cutover-gate.json"


class ProductionFallbackGateTests(unittest.TestCase):
    def test_committed_gate_records_only_formal_production_routes(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["phase"], "P3.1-production-fallback-cutover")
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blocking_issues"], 0)
        self.assertEqual(
            [item["selection_method"] for item in report["production_routes"]],
            ["exact_canonical_name", "exact_official_alias", "host_from_top_k"],
        )
        self.assertEqual(report["raster_handoff"], {"status": "raster_handoff_pending", "false_svg_success_artifacts": 0})
        self.assertEqual(report["legacy_isolation"]["rejected_methods"], ["tabler_composition", "programmatic_svg"])
        self.assertEqual(report["legacy_isolation"]["production_calls"], 0)
        self.assertEqual(report["static_route_check"]["legacy_imports_or_calls"], 0)
        self.assertTrue(report["p0_baseline_unchanged"])
        self.assertEqual(set(report["review_run"].values()), {0})


if __name__ == "__main__":
    unittest.main()
