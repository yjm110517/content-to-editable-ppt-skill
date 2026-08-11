from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from recovery_engine import RecoveryError, StageLedger, authorize_global_replan, authorize_targeted_revision, recovery_route


class TransientError(RuntimeError):
    code = "render_failed"


class RecoveryEngineTests(unittest.TestCase):
    def test_retry_is_bounded_to_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "input.json"
            source.write_text("{}", encoding="utf-8")
            output = root / "output.json"
            ledger = StageLedger(root / "stage-state.json", root=root)
            calls = 0

            def fail() -> None:
                nonlocal calls
                calls += 1
                raise TransientError("temporary")

            with self.assertRaises(TransientError):
                ledger.run("render", inputs=[source], outputs=[output], action=fail, retryable=lambda exc: isinstance(exc, TransientError))
            self.assertEqual(calls, 3)
            self.assertEqual(ledger.state["counters"]["technical_retries"], 2)

    def test_resume_reuses_passed_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "input.json"
            output = root / "output.json"
            source.write_text("{}", encoding="utf-8")
            calls = 0

            def build() -> None:
                nonlocal calls
                calls += 1
                output.write_text("built", encoding="utf-8")

            ledger = StageLedger(root / "stage-state.json", root=root)
            self.assertEqual(ledger.run("build", inputs=[source], outputs=[output], action=build), "passed")
            reloaded = StageLedger(root / "stage-state.json", root=root)
            self.assertEqual(reloaded.run("build", inputs=[source], outputs=[output], action=build, resume=True), "reused")
            self.assertEqual(calls, 1)

    def test_local_and_technical_routes_are_distinct(self) -> None:
        self.assertEqual(recovery_route("local_spec_failure"), "targeted_patch")
        self.assertEqual(recovery_route("technical_failure"), "technical_retry")
        self.assertEqual(recovery_route("global_semantic_failure"), "limited_full_replan")

    def test_full_replan_requires_evidence_and_is_limited(self) -> None:
        state = {"schema_version": "1.3", "task_id": "t", "request_sha256": "0" * 64, "state": "building", "current_iteration": 1, "max_iterations": 3, "history": []}
        with self.assertRaises(RecoveryError):
            authorize_global_replan(state, [])
        updated = authorize_global_replan(state, ["multiple unrelated groups are inconsistent"])
        self.assertEqual(updated["counters"]["full_semantic_replans"], 1)
        with self.assertRaises(RecoveryError):
            authorize_global_replan(updated, ["still global"])

    def test_targeted_revision_and_total_iteration_limits(self) -> None:
        state = {"schema_version": "1.3", "task_id": "t", "request_sha256": "0" * 64, "state": "review_revise", "current_iteration": 1, "max_iterations": 3, "history": []}
        second = authorize_targeted_revision(state)
        self.assertEqual(second["counters"]["targeted_revisions"], 1)
        third = authorize_targeted_revision(second)
        self.assertEqual(third["counters"]["targeted_revisions"], 2)
        with self.assertRaises(RecoveryError):
            authorize_targeted_revision(third)


if __name__ == "__main__":
    unittest.main()
