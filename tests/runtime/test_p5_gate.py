from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class P5GateTests(unittest.TestCase):
    def test_deterministic_gate_stops_at_live_review_pending(self) -> None:
        report = json.loads((ROOT / "reports" / "p5" / "p5-final-deck-delivery-gate.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "pending_live_evidence")
        self.assertEqual(report["deterministic_gate"], "pass")
        self.assertEqual(report["package_candidate_hash_closure"], "pass")
        self.assertEqual(report["formal_delivery_created"], False)
        self.assertEqual(report["does_not_satisfy_adr_040"], True)
        self.assertEqual(report["live_deck_review"], "pending")
        self.assertEqual(report["p5_overall"], "pending")
        self.assertEqual(report["critical"], 0)
        self.assertEqual(report["major"], 0)
        self.assertEqual(report["review_incomplete"], 0)
        self.assertEqual(report["unexpected_reviewer_calls"], 0)
        cases = {item["case_id"]: item for item in report["cases"]}
        self.assertEqual(set(cases), {"D03", "D05", "D08"})

    def test_d03_deterministic_chain_no_formal_delivery(self) -> None:
        report = json.loads((ROOT / "reports" / "p5" / "p5-final-deck-delivery-gate.json").read_text(encoding="utf-8"))
        d03 = next(item for item in report["cases"] if item["case_id"] == "D03")
        self.assertEqual(d03["status"], "pass")
        self.assertFalse(d03["formal_delivery_created"])
        self.assertTrue(d03["does_not_satisfy_adr_040"])
        self.assertEqual(d03["state"], "live_review_pending")

    def test_d05_d08_fixtures_no_live_calls(self) -> None:
        report = json.loads((ROOT / "reports" / "p5" / "p5-final-deck-delivery-gate.json").read_text(encoding="utf-8"))
        for item in report["cases"]:
            if item["case_id"] == "D03":
                continue
            self.assertEqual(item["status"], "pass")
            self.assertEqual(item["reviewer_calls"], 0)
            self.assertEqual(item["live_agent_calls"], 0)


if __name__ == "__main__":
    unittest.main()
