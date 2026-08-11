from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from agent_adapters import AgentCallLedger, FailureAdapter, FixtureAdapter
from reviewer_controller import apply_technical_degradation, run_reviewer_gate
from schema_utils import validate_schema, validate_semantics


SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"


class ReviewerControllerTests(unittest.TestCase):
    def test_major_is_revision_required_not_degradation(self) -> None:
        response = {
            "reviewer_recommendation": "revise",
            "issues": [{"severity": "major"}],
        }
        result = run_reviewer_gate(
            FixtureAdapter(response), ledger=AgentCallLedger(), task_id="t", iteration=1,
            call_id="review-1", structural_pass=True, content_pass=True, editability_pass=True,
        )
        self.assertEqual(result["status"], "revision_required")
        self.assertIsNone(result["technical_failure"])
        self.assertEqual(result["attempt_count"], 1)

    def test_technical_failure_degrades_only_when_all_gates_pass(self) -> None:
        ledger = AgentCallLedger()
        result = run_reviewer_gate(
            FailureAdapter("reviewer_timeout"), ledger=ledger, task_id="t", iteration=1,
            call_id="review-1", structural_pass=True, content_pass=True, editability_pass=True,
        )
        self.assertEqual(result["status"], "delivered_with_warnings")
        self.assertEqual(result["attempt_count"], 3)
        self.assertEqual(result["technical_retry_count"], 2)
        self.assertEqual(result["warning"], "visual review incomplete")
        self.assertEqual({item["role"] for item in ledger.calls}, {"reviewer"})
        validate_schema("reviewer_technical_failure", result["technical_failure"], SCHEMA_DIR)

    def test_technical_failure_cannot_bypass_content_gate(self) -> None:
        result = run_reviewer_gate(
            FailureAdapter("reviewer_unavailable"), ledger=AgentCallLedger(), task_id="t", iteration=1,
            call_id="review-1", structural_pass=True, content_pass=False, editability_pass=True,
        )
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(result["warning"])

    def test_degraded_delivery_is_written_to_authoritative_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = run_reviewer_gate(
                FailureAdapter("reviewer_timeout"), ledger=AgentCallLedger(), task_id="t", iteration=1,
                call_id="review-1", structural_pass=True, content_pass=True, editability_pass=True,
            )
            failure_path = root / "reviewer_technical_failure.json"
            failure_path.write_text(json.dumps(result["technical_failure"]), encoding="utf-8")
            state = {
                "schema_version": "1.4", "task_id": "t", "request_sha256": "0" * 64,
                "state": "reviewing", "current_iteration": 1, "max_iterations": 3, "history": [],
                "current_stage": "reviewer", "counters": {"planner_calls": 1, "reviewer_calls": 3, "full_semantic_replans": 0, "targeted_revisions": 0, "technical_retries": 2, "runtime_repairs": 0},
                "stages": {}, "last_failure": None, "reclassifications": [],
            }
            updated = apply_technical_degradation(state, result, failure_path=failure_path, work_root=root)
            self.assertEqual(updated["state"], "delivered_with_warnings")
            validate_schema("run_state", updated, SCHEMA_DIR)
            validate_semantics("run_state", updated)


if __name__ == "__main__":
    unittest.main()
