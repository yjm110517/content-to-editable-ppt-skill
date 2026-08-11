from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from canonical_artifact import canonical_sha256
from manage_wireframe import _feedback, _preview
from schema_utils import ContractError
from wireframe_state import advance, initial_state


H = "a" * 64
NOW = "2026-08-11T00:00:00Z"


def rendered_state() -> dict:
    state = initial_state(task_id="t", deck_id="D", absolute_host_model_invocation_ceiling=6)
    for event in ("start_input_validation", "inputs_accepted"):
        state = advance(state, event=event, timestamp_utc=NOW)
    state = advance(state, event="start_initial_planning", pass_id="p", host_model_invocation_id="h1", timestamp_utc=NOW)
    for event in ("candidate_specs_ready", "start_spec_validation", "specs_accepted", "start_rendering", "rendering_complete"):
        state = advance(state, event=event, timestamp_utc=NOW)
    state["current_artifacts"]["wireframe_manifest_sha256"] = H
    return state


class P2PreviewFeedbackTests(unittest.TestCase):
    def write(self, path: Path, document: dict) -> None:
        path.write_text(json.dumps(document), encoding="utf-8")

    def test_user_visible_preview_waits_and_feedback_closes_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path, preview_path, feedback_path = root / "state.json", root / "preview.json", root / "feedback.json"
            self.write(state_path, rendered_state())
            preview = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "pv", "deck_id": "D", "wireframe_manifest_sha256": H, "mode": "user_visible", "decided_by": "user", "visible_slide_ids": ["S01"], "pause_for_feedback": True, "decision_reason": "review", "user_message_sha256": H, "presented_at_utc": NOW}
            self.write(preview_path, preview)
            state = _preview(SimpleNamespace(state=state_path, preview=preview_path))
            self.assertEqual(state["state"], "awaiting_wireframe_feedback")
            feedback = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "feedback_id": "f", "deck_id": "D", "wireframe_manifest_sha256": H, "decision": "continue", "affected_slide_ids": [], "user_message_sha256": H, "created_at_utc": NOW}
            self.write(feedback_path, feedback)
            state = _feedback(SimpleNamespace(state=state_path, feedback=feedback_path))
            self.assertEqual(state["state"], "p2_complete")

    def test_internal_preview_completes_without_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path, preview_path = root / "state.json", root / "preview.json"
            self.write(state_path, rendered_state())
            preview = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "pv", "deck_id": "D", "wireframe_manifest_sha256": H, "mode": "internal_only", "decided_by": "host", "visible_slide_ids": [], "pause_for_feedback": False, "decision_reason": "low risk", "user_message_sha256": None, "presented_at_utc": None}
            self.write(preview_path, preview)
            self.assertEqual(_preview(SimpleNamespace(state=state_path, preview=preview_path))["state"], "p2_complete")

    def test_stale_preview_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path, preview_path = root / "state.json", root / "preview.json"
            self.write(state_path, rendered_state())
            preview = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "pv", "deck_id": "D", "wireframe_manifest_sha256": canonical_sha256({"stale": True}), "mode": "internal_only", "decided_by": "host", "visible_slide_ids": [], "pause_for_feedback": False, "decision_reason": "low risk", "user_message_sha256": None, "presented_at_utc": None}
            self.write(preview_path, preview)
            with self.assertRaises(ContractError):
                _preview(SimpleNamespace(state=state_path, preview=preview_path))


if __name__ == "__main__":
    unittest.main()
