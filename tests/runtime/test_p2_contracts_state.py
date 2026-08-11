from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from schema_utils import validate_schema
from wireframe_state import WireframeStateError, advance, initial_state


SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"
H = "a" * 64
NOW = "2026-08-11T00:00:00Z"


def region(region_id: str, role: str, refs: list[str], *, parent: str | None = None, level: int = 1) -> dict:
    return {"region_id": region_id, "role": role, "parent_region_id": parent, "bbox": {"x": 500, "y": 500, "w": 4000, "h": 1500}, "content_refs": refs, "semantic_source_refs": [], "hierarchy_level": level, "emphasis": "primary", "z_index": 10, "overlap_group": None}


class P2ContractsAndStateTests(unittest.TestCase):
    def test_all_p2_contracts_parse(self) -> None:
        layout = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "lr1", "deck_id": "D03", "deck_request_sha256": H, "revision": 1, "parent_sha256": None, "density": "balanced", "preferred_region_structure": ["modular"], "required_visual_zones": [], "layout_direction": "left_to_right", "reserved_areas": {"header_height": 0, "footer_height": 500}, "cross_slide_structural_consistency": "moderate", "layout_constraints_sha256": H, "source_classifications": [], "created_at_utc": NOW}
        spec = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "wf-S01-r1", "deck_id": "D03", "slide_id": "S01", "revision": 1, "parent_sha256": None, "authority": {"slide_content_payload_sha256": H, "layout_constraints_sha256": H, "page_metadata_sha256": H, "wireframe_input_sha256": H}, "coordinate_system": "normalized_10000", "output_ratio": "16:9", "layout_pattern": "two_column", "focal_region_id": "R1", "regions": [region("R1", "title", ["S01-TITLE"]), region("R2", "content", ["S01-C01"])], "relationships": [], "created_at_utc": NOW}
        manifest = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "wfm-r1", "deck_id": "D03", "revision": 1, "parent_sha256": None, "output_ratio": "16:9", "approved_outline_sha256": H, "slide_content_manifest_sha256": H, "layout_requirements_sha256": H, "slides": [{"slide_id": "S01", "order": 1, "spec_path": "specs/S01-r001.json", "spec_sha256": H, "wireframe_input_sha256": H, "svg_path": None, "svg_sha256": None, "build_status": "rebuilt"}], "created_at_utc": NOW}
        report = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "report_id": "vr1", "deck_id": "D03", "candidate_manifest_sha256": H, "status": "pass", "issues": [], "validated_at_utc": NOW}
        correction = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "correction_id": "c1", "deck_id": "D03", "pass_id": "p1", "attempt": 1, "host_model_invocation_id": "h2", "candidate_manifest_sha256": H, "validation_report_sha256": H, "operations": [{"validation_issue_id": "i1", "slide_id": "S01", "target_type": "region", "target_id": "R1", "field": "bbox", "before": {"x": 0}, "after": {"x": 1}}], "created_at_utc": NOW}
        preview = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "pv1", "deck_id": "D03", "wireframe_manifest_sha256": H, "mode": "internal_only", "decided_by": "user", "visible_slide_ids": [], "pause_for_feedback": False, "decision_reason": "continue", "user_message_sha256": H, "presented_at_utc": None}
        feedback = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "feedback_id": "f1", "deck_id": "D03", "wireframe_manifest_sha256": H, "decision": "continue", "affected_slide_ids": [], "user_message_sha256": H, "created_at_utc": NOW}
        state = initial_state(task_id="t", deck_id="D03", absolute_host_model_invocation_ceiling=6)
        for kind, document in {"wireframe_layout_requirements": layout, "wireframe_spec": spec, "wireframe_manifest": manifest, "wireframe_validation_report": report, "wireframe_correction_record": correction, "wireframe_preview": preview, "wireframe_feedback": feedback, "wireframe_state": state}.items():
            with self.subTest(kind=kind):
                validate_schema(kind, document, SCHEMA_DIR)

    def test_state_tracks_logical_passes_and_real_invocations(self) -> None:
        state = initial_state(task_id="t", deck_id="D03", absolute_host_model_invocation_ceiling=6)
        state = advance(state, event="start_input_validation", timestamp_utc=NOW)
        state = advance(state, event="inputs_accepted", timestamp_utc=NOW)
        state = advance(state, event="start_initial_planning", pass_id="initial", host_model_invocation_id="h1", timestamp_utc=NOW)
        state = advance(state, event="candidate_specs_ready", timestamp_utc=NOW)
        state = advance(state, event="start_spec_validation", timestamp_utc=NOW)
        for invocation in ("h2", "h3"):
            state = advance(state, event="contract_correction_required", timestamp_utc=NOW)
            state = advance(state, event="start_contract_correction", host_model_invocation_id=invocation, timestamp_utc=NOW)
            state = advance(state, event="contract_correction_applied", timestamp_utc=NOW)
            state = advance(state, event="start_spec_validation", timestamp_utc=NOW)
        self.assertEqual(state["counters"]["host_wireframe_initial_pass_count"], 1)
        self.assertEqual(state["counters"]["host_wireframe_contract_correction_count"], 2)
        self.assertEqual(state["counters"]["host_model_invocation_count"], 3)
        state = advance(state, event="contract_correction_required", timestamp_utc=NOW)
        with self.assertRaises(WireframeStateError):
            advance(state, event="start_contract_correction", host_model_invocation_id="h4", timestamp_utc=NOW)

    def test_feedback_wait_loop_and_revision_budget(self) -> None:
        state = initial_state(task_id="t", deck_id="D03", absolute_host_model_invocation_ceiling=6)
        for event in ("start_input_validation", "inputs_accepted"):
            state = advance(state, event=event, timestamp_utc=NOW)
        state = advance(state, event="start_initial_planning", pass_id="initial", host_model_invocation_id="h1", timestamp_utc=NOW)
        for event in ("candidate_specs_ready", "start_spec_validation", "specs_accepted", "start_rendering", "rendering_complete", "preview_recorded", "wait_for_feedback"):
            state = advance(state, event=event, timestamp_utc=NOW)
        state = advance(state, event="feedback_changes_requested", user_evidence_sha256=H, affected_slide_ids=["S01"], timestamp_utc=NOW)
        state = advance(state, event="start_revision_planning", pass_id="revision-1", user_evidence_sha256=H, host_model_invocation_id="h2", timestamp_utc=NOW)
        self.assertEqual(state["counters"]["host_wireframe_revision_pass_count"], 1)
        self.assertEqual(state["counters"]["host_model_invocation_count"], 2)


if __name__ == "__main__":
    unittest.main()
