from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys_path = str(ROOT / "content-to-editable-ppt" / "scripts")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from delivery_policy import evaluate_delivery_policy  # noqa: E402
from manage_delivery import decision_policy_summary  # noqa: E402
from schema_utils import ContractError  # noqa: E402


class P5DeliveryPolicyTests(unittest.TestCase):
    def test_clean_pass(self) -> None:
        policy = evaluate_delivery_policy(severity_counts={"critical": 0, "major": 0, "minor": 0, "suggestion": 2}, review_incomplete=0, unexpected_reviewer_calls=0)
        self.assertEqual(policy["policy_status"], "pass")
        self.assertEqual(policy["decision_state"], "delivery_approved")

    def test_minor_requires_acceptance(self) -> None:
        policy = evaluate_delivery_policy(severity_counts={"critical": 0, "major": 0, "minor": 1, "suggestion": 0}, review_incomplete=0, unexpected_reviewer_calls=0)
        self.assertEqual(policy["policy_status"], "awaiting_warning_acceptance")
        self.assertEqual(policy["decision_state"], "awaiting_warning_acceptance")

    def test_critical_not_deliverable(self) -> None:
        policy = evaluate_delivery_policy(severity_counts={"critical": 1, "major": 0, "minor": 0, "suggestion": 0}, review_incomplete=0, unexpected_reviewer_calls=0)
        self.assertEqual(policy["policy_status"], "not_deliverable")
        self.assertEqual(policy["decision_state"], "upstream_revision_required")

    def test_major_not_deliverable(self) -> None:
        policy = evaluate_delivery_policy(severity_counts={"critical": 0, "major": 2, "minor": 0, "suggestion": 0}, review_incomplete=0, unexpected_reviewer_calls=0)
        self.assertEqual(policy["policy_status"], "not_deliverable")

    def test_review_incomplete_blocks(self) -> None:
        policy = evaluate_delivery_policy(severity_counts={"critical": 0, "major": 0, "minor": 0, "suggestion": 0}, review_incomplete=1, unexpected_reviewer_calls=0)
        self.assertEqual(policy["policy_status"], "not_deliverable")

    def test_unexpected_reviewer_calls_block(self) -> None:
        policy = evaluate_delivery_policy(severity_counts={"critical": 0, "major": 0, "minor": 0, "suggestion": 0}, review_incomplete=0, unexpected_reviewer_calls=1)
        self.assertEqual(policy["policy_status"], "not_deliverable")

    def test_negative_counts_rejected(self) -> None:
        with self.assertRaises(ContractError):
            evaluate_delivery_policy(severity_counts={"critical": -1, "major": 0, "minor": 0, "suggestion": 0}, review_incomplete=0, unexpected_reviewer_calls=0)

    def test_decision_summary_excludes_non_authorizing_suggestions(self) -> None:
        summary = decision_policy_summary({
            "severity_counts": {"critical": 0, "major": 0, "minor": 0, "suggestion": 2},
            "review_incomplete": 0,
            "unexpected_reviewer_calls": 0,
        })
        self.assertEqual(set(summary), {"critical", "major", "minor", "review_incomplete", "unexpected_reviewer_calls"})


if __name__ == "__main__":
    unittest.main()
