from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from schema_utils import validate_schema
from wireframe_state import WireframeStateError, authorize_revision_budget, consume_correction, initial_state, record_feedback, record_preview, request_visual_revision, start_planning, submit_validation


H = "a" * 64


class P2MarkdownContractsStateTests(unittest.TestCase):
    def test_all_markdown_p2_schemas_parse(self) -> None:
        schema_dir = ROOT / "content-to-editable-ppt" / "schemas"
        for kind in ("markdown_wireframe_candidate", "markdown_wireframe_manifest", "markdown_wireframe_validation_report", "markdown_wireframe_correction_record", "markdown_wireframe_preview", "markdown_wireframe_feedback", "markdown_wireframe_state"):
            with self.subTest(kind=kind):
                self.assertTrue((schema_dir / __import__("schema_utils").SCHEMA_FILES[kind]).is_file())

    def test_state_tracks_initial_and_two_corrections(self) -> None:
        state = initial_state(task_id="T", deck_id="D", approved_outline_sha256=H, slide_content_manifest_sha256=H, absolute_host_model_invocation_ceiling=6)
        state = submit_validation(state, candidate_sha256=H, report_sha256=H, status="correctable", host_model_invocation_id="h1", pass_id="p1")
        state = consume_correction(state, host_model_invocation_id="h2")
        state = submit_validation(state, candidate_sha256=H, report_sha256=H, status="correctable", host_model_invocation_id="ignored", pass_id="p1")
        state = consume_correction(state, host_model_invocation_id="h3")
        self.assertEqual(state["counters"]["host_model_invocation_count"], 3)
        self.assertEqual(state["counters"]["host_wireframe_contract_correction_count"], 2)
        state = submit_validation(state, candidate_sha256=H, report_sha256=H, status="correctable", host_model_invocation_id="ignored", pass_id="p1")
        with self.assertRaises(WireframeStateError):
            consume_correction(state, host_model_invocation_id="h4")

    def test_content_feedback_is_terminal_but_layout_feedback_can_start_revision(self) -> None:
        base = initial_state(task_id="T", deck_id="D", approved_outline_sha256=H, slide_content_manifest_sha256=H)
        base["state"] = "ready_for_preview"
        waiting = record_preview(base, preview_sha256=H, mode="user_visible", user_message_sha256=H)
        content = record_feedback(waiting, feedback_sha256=H, decision="changes_requested", scope="content", affected_slide_ids=["S01"], user_message_sha256=H)
        self.assertEqual(content["state"], "p1_revision_required")
        with self.assertRaises(WireframeStateError):
            start_planning(content, pass_id="r2", host_model_invocation_id="h2", user_evidence_sha256=H)
        layout = record_feedback(waiting, feedback_sha256=H, decision="changes_requested", scope="layout", affected_slide_ids=["S01"], user_message_sha256=H)
        revised = start_planning(layout, pass_id="r2", host_model_invocation_id="h2", user_evidence_sha256=H)
        self.assertEqual(revised["counters"]["host_wireframe_revision_pass_count"], 1)

    def test_completed_p2_accepts_explicit_visual_storyboard_revision(self) -> None:
        state = initial_state(task_id="T", deck_id="D", approved_outline_sha256=H, slide_content_manifest_sha256=H, absolute_host_model_invocation_ceiling=3)
        state["counters"]["host_model_invocation_count"] = 3
        state["state"] = "p2_complete"; state["current_revision"] = 1
        revised = request_visual_revision(state, feedback_sha256=H, affected_slide_ids=["S01"], user_message_sha256=H)
        self.assertEqual(revised["state"], "revision_requested")
        self.assertEqual(revised["changed_slide_ids"], ["S01"])
        self.assertEqual(revised["budgets"]["absolute_host_model_invocation_ceiling"], 6)
        planned = start_planning(revised, pass_id="r2", host_model_invocation_id="h2", user_evidence_sha256=H)
        self.assertEqual(planned["state"], "wireframe_planning")
        with self.assertRaises(WireframeStateError):
            request_visual_revision(state, feedback_sha256=H, affected_slide_ids=[], user_message_sha256=H)

    def test_legacy_pending_revision_can_authorize_budget_once(self) -> None:
        state = initial_state(task_id="T", deck_id="D", approved_outline_sha256=H, slide_content_manifest_sha256=H, absolute_host_model_invocation_ceiling=3)
        state["state"]="revision_requested"; state["changed_slide_ids"]=["S01"]; state["counters"]["host_model_invocation_count"]=3
        state["history"].append({"from":"p2_complete","to":"revision_requested","event":"visual_storyboard_changes_requested","artifact_sha256":H,"user_evidence_sha256":H,"host_model_invocation_id":None,"affected_slide_ids":["S01"],"timestamp_utc":"2026-08-24T00:00:00Z"})
        authorized=authorize_revision_budget(state,user_evidence_sha256=H)
        self.assertEqual(authorized["budgets"]["absolute_host_model_invocation_ceiling"],6)
        with self.assertRaises(WireframeStateError):authorize_revision_budget(authorized,user_evidence_sha256=H)

    def test_state_schema_accepts_new_state(self) -> None:
        state = initial_state(task_id="T", deck_id="D", approved_outline_sha256=H, slide_content_manifest_sha256=H)
        validate_schema("markdown_wireframe_state", state, ROOT / "content-to-editable-ppt" / "schemas")


if __name__ == "__main__":
    unittest.main()
