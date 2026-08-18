from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys_path = str(ROOT / "content-to-editable-ppt" / "scripts")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from delivery_state import initial_delivery_state, transition  # noqa: E402
from schema_utils import ContractError  # noqa: E402


class P5DeliveryStateTests(unittest.TestCase):
    def test_initial_state_and_first_transition(self) -> None:
        state = initial_delivery_state("D03", "a" * 64)
        self.assertEqual(state["state"], "p4_complete")
        self.assertEqual(state["budgets"]["exception_batch_size"], 4)
        self.assertEqual(state["budgets"]["exception_batch_calls"], 2)
        advanced = transition(state, "p5_preflight")
        self.assertEqual(advanced["state"], "p5_preflight")
        self.assertEqual(advanced["history"][-1]["from"], "p4_complete")
        self.assertTrue(advanced["history"][-1]["previous_sha256"])

    def test_deterministic_chain_to_live_review_pending(self) -> None:
        state = initial_delivery_state("D03", "a" * 64)
        chain = ["p5_preflight", "final_integrity_check", "deterministic_deck_qa", "roundtrip_check", "exception_review_routing", "deck_consistency_review", "live_review_pending"]
        for target in chain:
            state = transition(state, target)
        self.assertEqual(state["state"], "live_review_pending")
        self.assertEqual(len(state["history"]), len(chain))

    def test_illegal_transition_rejected(self) -> None:
        state = initial_delivery_state("D03", "a" * 64)
        with self.assertRaises(ContractError):
            transition(state, "delivered")

    def test_formal_path_requires_live_review_consumption(self) -> None:
        # fixture 路径必须停在 live_review_pending；从 live_review_pending 可直接进入 evaluating_delivery_policy
        state = initial_delivery_state("D03", "a" * 64)
        for target in ["p5_preflight", "final_integrity_check", "deterministic_deck_qa", "roundtrip_check", "exception_review_routing", "deck_consistency_review", "live_review_pending", "evaluating_delivery_policy", "delivery_approved", "packaging", "delivered"]:
            state = transition(state, target)
        self.assertEqual(state["state"], "delivered")


if __name__ == "__main__":
    unittest.main()
