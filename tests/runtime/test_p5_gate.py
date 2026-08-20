from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class P5GateTests(unittest.TestCase):
    def test_final_gate_records_live_delivery_closure(self) -> None:
        report = json.loads((ROOT / "reports" / "p5" / "p5-final-deck-delivery-gate.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["deterministic_gate"], "pass")
        self.assertTrue(report["formal_delivery_created"])
        self.assertFalse(report["does_not_satisfy_adr_040"])
        self.assertEqual(report["live_deck_review"], "complete")
        self.assertEqual(report["p5_overall"], "pass")
        self.assertEqual(report["state"], "delivered")
        self.assertEqual(report["delivery_artifact_hash_closure"], "pass")
        self.assertEqual(report["formal_delivery_file_count"], 7)
        self.assertRegex(report["resolved_model_identity_sha256"], "^[a-f0-9]{64}$")
        self.assertRegex(report["transport_request_sha256"], "^[a-f0-9]{64}$")
        self.assertEqual(report["critical"], 0)
        self.assertEqual(report["major"], 0)
        self.assertEqual(report["review_incomplete"], 0)
        self.assertEqual(report["unexpected_reviewer_calls"], 0)
        self.assertEqual(report["reviewer_technical_retry_count"], 1)

    def test_delivered_pptx_matches_frozen_decision(self) -> None:
        report = json.loads((ROOT / "reports" / "p5" / "p5-final-deck-delivery-gate.json").read_text(encoding="utf-8"))
        decision = json.loads((ROOT / "reports" / "p5" / "evidence" / "d03-live-deck-consistency" / "delivery-decision.json").read_text(encoding="utf-8"))
        self.assertEqual(decision["status"], "pass")
        self.assertEqual(report["delivered_pptx_sha256"], decision["delivered_pptx_sha256"])

    def test_frozen_live_evidence_is_production_v11(self) -> None:
        root = ROOT / "reports" / "p5" / "evidence" / "d03-live-deck-consistency" / "reviewer-evidence"
        response = json.loads((root / "finalized_response.json").read_text(encoding="utf-8"))
        call_record = json.loads((root / "call_record.json").read_text(encoding="utf-8"))
        self.assertEqual(response["schema_version"], "1.1")
        self.assertTrue(call_record["live"])
        self.assertEqual(call_record["input_profile"], "deck_consistency")


if __name__ == "__main__":
    unittest.main()
