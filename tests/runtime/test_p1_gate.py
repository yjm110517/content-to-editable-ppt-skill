from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "content-planning"))

from p1_content_planning_eval import evaluate_case, load_fixtures


class P1GateTests(unittest.TestCase):
    def test_d03_d05_d08_frozen_content_planning_oracles(self) -> None:
        fixture = load_fixtures()
        results = {item["case_id"]: evaluate_case(item, fixture["fixed_timestamp_utc"]) for item in fixture["cases"]}
        self.assertEqual({key: item["pages"] for key, item in results.items()}, {"D03": 3, "D05": 5, "D08": 8})
        self.assertEqual(results["D03"]["host_revision_pass_count"], 1)
        self.assertEqual(results["D05"]["host_revision_pass_count"], 0)
        self.assertEqual(results["D08"]["host_revision_pass_count"], 0)
        for result in results.values():
            self.assertEqual(result["content_projection_drift"], 0)
            self.assertEqual(result["host_planning_pass_count"], 1)
            self.assertEqual(result["automatic_regeneration_count"], 0)
            self.assertEqual(result["planner_calls"], 0)
            self.assertEqual(result["reviewer_calls"], 0)


if __name__ == "__main__":
    unittest.main()
