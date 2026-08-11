from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from content_plan_state import ContentPlanStateError, advance, initial_state
from schema_utils import validate_schema


SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"
HASH = "a" * 64
NOW = "2026-08-11T00:00:00Z"


class P1StateTests(unittest.TestCase):
    def step(self, state: dict, event: str, **kwargs: str) -> dict:
        return advance(state, event=event, timestamp_utc=NOW, **kwargs)

    def test_content_path_enforces_single_initial_pass(self) -> None:
        state = initial_state(task_id="p1", deck_id="D03")
        for event in ("start_routing", "route_content_to_ppt", "materials_ready", "initial_candidate_ready"):
            state = self.step(state, event)
        self.assertEqual(state["state"], "candidate_ready")
        self.assertEqual(state["counters"]["host_planning_pass_count"], 1)
        with self.assertRaises(ContentPlanStateError):
            self.step(state, "initial_candidate_ready")
        validate_schema("content_plan_state", state, SCHEMA_DIR)

    def test_clarification_and_material_resolution_are_closed_loops(self) -> None:
        state = initial_state(task_id="p1", deck_id="D03")
        for event in ("start_routing", "request_route_clarification", "clarification_received", "route_content_to_ppt", "block_required_material", "material_resolution_received", "materials_ready"):
            state = self.step(state, event)
        self.assertEqual(state["state"], "materials_ready")

    def test_revision_requires_user_evidence_and_increments_only_once(self) -> None:
        state = initial_state(task_id="p1", deck_id="D03")
        for event in ("start_routing", "route_content_to_ppt", "materials_ready", "initial_candidate_ready", "request_outline_confirmation"):
            state = self.step(state, event)
        with self.assertRaises(ContentPlanStateError):
            self.step(state, "changes_requested")
        state = self.step(state, "changes_requested", user_evidence_sha256=HASH)
        state = self.step(state, "candidate_revised", user_evidence_sha256=HASH)
        self.assertEqual(state["counters"]["host_revision_pass_count"], 1)
        self.assertEqual(state["counters"]["automatic_regeneration_count"], 0)

    def test_image_route_bypasses_p1(self) -> None:
        state = initial_state(task_id="image", deck_id="single")
        state = self.step(state, "start_routing")
        state = self.step(state, "route_image_to_ppt")
        self.assertEqual(state["state"], "p1_bypassed")


if __name__ == "__main__":
    unittest.main()
