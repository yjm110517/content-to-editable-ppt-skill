from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from canonical_artifact import canonical_sha256
from deterministic_project_slide_content import build_projection
from manage_wireframe import _accept, _feedback, _preview, _projection_bundle, _validate_manifest_authority
from schema_utils import ContractError
from wireframe_state import WireframeStateError, advance, initial_state
from tests.runtime.test_p2_wireframe_rules import approved, requirements, spec


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
    state["page_results"] = [
        {"slide_id": "S01", "wireframe_input_sha256": H, "build_status": "rebuilt", "spec_sha256": H, "svg_sha256": H},
        {"slide_id": "S02", "wireframe_input_sha256": H, "build_status": "rebuilt", "spec_sha256": H, "svg_sha256": H},
    ]
    return state


def preview(*, deck_id: str = "D", mode: str = "user_visible", manifest_sha256: str = H) -> dict:
    internal = mode == "internal_only"
    return {
        "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "pv",
        "deck_id": deck_id, "wireframe_manifest_sha256": manifest_sha256, "mode": mode,
        "decided_by": "host" if internal else "user", "visible_slide_ids": [] if internal else ["S01"],
        "pause_for_feedback": not internal, "decision_reason": "review", "user_message_sha256": None if internal else H,
        "presented_at_utc": None if internal else NOW,
    }


def feedback(*, decision: str = "continue", scope: str = "none", slides: list[str] | None = None, deck_id: str = "D", preview_sha256: str = H) -> dict:
    return {
        "schema_version": "1.1", "canonicalization_version": "p1-rfc8785-nfc-1", "feedback_id": "f",
        "deck_id": deck_id, "wireframe_manifest_sha256": H, "wireframe_preview_sha256": preview_sha256,
        "decision": decision, "change_scope": scope, "affected_slide_ids": list(slides or []),
        "user_message_sha256": H, "created_at_utc": NOW,
    }


class P2PreviewFeedbackTests(unittest.TestCase):
    def write(self, path: Path, document: dict) -> None:
        path.write_text(json.dumps(document), encoding="utf-8")

    def record_preview(self, root: Path, state: dict, document: dict | None = None) -> tuple[Path, dict]:
        state_path, preview_path = root / "state.json", root / "preview.json"
        value = document or preview()
        self.write(state_path, state)
        self.write(preview_path, value)
        return state_path, _preview(SimpleNamespace(state=state_path, preview=preview_path))

    def test_user_visible_preview_and_continue_close_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path, state = self.record_preview(root, rendered_state())
            self.assertEqual(state["state"], "awaiting_wireframe_feedback")
            self.assertEqual(state["current_artifacts"]["preview_sha256"], canonical_sha256(preview()))
            feedback_path = root / "feedback.json"
            self.write(feedback_path, feedback(preview_sha256=canonical_sha256(preview())))
            state = _feedback(SimpleNamespace(state=state_path, feedback=feedback_path))
            self.assertEqual(state["state"], "p2_complete")
            self.assertEqual(state["changed_slide_ids"], [])

    def test_internal_preview_completes_without_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, state = self.record_preview(Path(temporary), rendered_state(), preview(mode="internal_only"))
            self.assertEqual(state["state"], "p2_complete")

    def test_layout_and_content_feedback_route_separately(self) -> None:
        for scope, expected in (("layout", "revision_requested"), ("content", "p1_revision_required")):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                state_path, before = self.record_preview(root, rendered_state())
                feedback_path = root / "feedback.json"
                self.write(feedback_path, feedback(decision="changes_requested", scope=scope, slides=["S02"], preview_sha256=before["current_artifacts"]["preview_sha256"]))
                after = _feedback(SimpleNamespace(state=state_path, feedback=feedback_path))
                self.assertEqual(after["state"], expected)
                self.assertEqual(after["changed_slide_ids"], ["S02"])
                self.assertEqual(after["counters"]["host_model_invocation_count"], 1)
                if scope == "content":
                    with self.assertRaises(WireframeStateError):
                        advance(after, event="start_revision_planning", pass_id="p2", user_evidence_sha256=H, host_model_invocation_id="h2")

    def test_cross_deck_stale_unknown_and_replayed_inputs_preserve_state(self) -> None:
        bad_previews = (preview(deck_id="OTHER"), preview(manifest_sha256="b" * 64), {**preview(), "visible_slide_ids": ["S99"]})
        for document in bad_previews:
            with self.subTest(preview=document), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                state_path, preview_path = root / "state.json", root / "preview.json"
                self.write(state_path, rendered_state()); self.write(preview_path, document)
                before = state_path.read_bytes()
                with self.assertRaises((ContractError, WireframeStateError)):
                    _preview(SimpleNamespace(state=state_path, preview=preview_path))
                self.assertEqual(state_path.read_bytes(), before)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path, waiting = self.record_preview(root, rendered_state())
            current_preview = waiting["current_artifacts"]["preview_sha256"]
            bad_feedback = (
                feedback(deck_id="OTHER", preview_sha256=current_preview),
                {**feedback(preview_sha256=current_preview), "wireframe_manifest_sha256": "b" * 64},
                feedback(preview_sha256="b" * 64),
                feedback(decision="changes_requested", scope="layout", slides=["S99"], preview_sha256=current_preview),
            )
            for index, document in enumerate(bad_feedback):
                feedback_path = root / f"feedback-{index}.json"
                self.write(feedback_path, document)
                before = state_path.read_bytes()
                with self.assertRaises((ContractError, WireframeStateError)):
                    _feedback(SimpleNamespace(state=state_path, feedback=feedback_path))
                self.assertEqual(state_path.read_bytes(), before)

            valid_path = root / "feedback-valid.json"
            self.write(valid_path, feedback(preview_sha256=current_preview))
            _feedback(SimpleNamespace(state=state_path, feedback=valid_path))
            consumed = state_path.read_bytes()
            with self.assertRaises(WireframeStateError):
                _feedback(SimpleNamespace(state=state_path, feedback=valid_path))
            self.assertEqual(state_path.read_bytes(), consumed)

    def test_invalid_scope_combinations_are_rejected(self) -> None:
        documents = (
            feedback(decision="continue", scope="layout", slides=[]),
            feedback(decision="changes_requested", scope="none", slides=["S01"]),
            feedback(decision="changes_requested", scope="layout", slides=[]),
        )
        for document in documents:
            with self.subTest(document=document), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                state_path, waiting = self.record_preview(root, rendered_state())
                document["wireframe_preview_sha256"] = waiting["current_artifacts"]["preview_sha256"]
                path = root / "feedback.json"; self.write(path, document)
                before = state_path.read_bytes()
                with self.assertRaises(ContractError):
                    _feedback(SimpleNamespace(state=state_path, feedback=path))
                self.assertEqual(state_path.read_bytes(), before)

    def test_accept_specs_binds_actual_outline_and_layout_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outline, layout = approved(), requirements()
            state = initial_state(task_id="t", deck_id="D")
            for event in ("start_input_validation", "inputs_accepted"):
                state = advance(state, event=event, timestamp_utc=NOW)
            state = advance(state, event="start_initial_planning", pass_id="p", host_model_invocation_id="h1", timestamp_utc=NOW)
            for event in ("candidate_specs_ready", "start_spec_validation", "specs_accepted"):
                state = advance(state, event=event, timestamp_utc=NOW)
            state["current_artifacts"]["approved_outline_sha256"] = canonical_sha256(outline)
            state["current_artifacts"]["layout_requirements_sha256"] = canonical_sha256(layout)
            state["current_artifacts"]["slide_content_manifest_sha256"] = H
            state_path, outline_path, layout_path = root / "state.json", root / "outline.json", root / "layout.json"
            spec_dir, output = root / "specs", root / "manifest.json"
            spec_dir.mkdir()
            self.write(state_path, state); self.write(outline_path, outline); self.write(layout_path, layout); self.write(spec_dir / "S01-r001.json", spec())
            args = SimpleNamespace(state=state_path, spec_dir=spec_dir, approved_outline=outline_path, layout_requirements=layout_path, output_ratio="16:9", manifest_output=output, artifact_id="m", revision=1, previous_manifest=None, timestamp_utc=NOW)
            _accept(args)
            self.assertTrue(output.is_file())

            for path, document in (
                (outline_path, {**outline, "artifact_id": "tampered"}),
                (layout_path, {**layout, "artifact_id": "tampered"}),
            ):
                with self.subTest(path=path.name):
                    self.write(outline_path, outline); self.write(layout_path, layout); output.unlink(missing_ok=True)
                    self.write(path, document)
                    state_before = state_path.read_bytes()
                    with self.assertRaises(ContractError):
                        _accept(args)
                    self.assertFalse(output.exists())
                    self.assertEqual(state_path.read_bytes(), state_before)

    def test_manifest_authority_tampering_is_rejected(self) -> None:
        state = initial_state(task_id="t", deck_id="D")
        state["current_artifacts"].update({
            "approved_outline_sha256": "a" * 64,
            "slide_content_manifest_sha256": "b" * 64,
            "layout_requirements_sha256": "c" * 64,
        })
        manifest = {
            "approved_outline_sha256": "a" * 64,
            "slide_content_manifest_sha256": "b" * 64,
            "layout_requirements_sha256": "c" * 64,
        }
        _validate_manifest_authority(state, manifest)
        for field in manifest:
            with self.subTest(field=field):
                tampered = {**manifest, field: "d" * 64}
                with self.assertRaises(ContractError) as caught:
                    _validate_manifest_authority(state, tampered)
                self.assertIn("authority_hash_mismatch", {item["code"] for item in caught.exception.errors})

    def test_accept_specs_consumes_exact_feedback_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outline, layout = approved(), requirements()
            state = initial_state(task_id="t", deck_id="D")
            for event in ("start_input_validation", "inputs_accepted"):
                state = advance(state, event=event, timestamp_utc=NOW)
            state = advance(state, event="start_initial_planning", pass_id="p", host_model_invocation_id="h1", timestamp_utc=NOW)
            for event in ("candidate_specs_ready", "start_spec_validation", "specs_accepted"):
                state = advance(state, event=event, timestamp_utc=NOW)
            state["current_artifacts"].update({"approved_outline_sha256": canonical_sha256(outline), "layout_requirements_sha256": canonical_sha256(layout), "slide_content_manifest_sha256": H})
            state["changed_slide_ids"] = ["S01"]
            state_path, outline_path, layout_path = root / "state.json", root / "outline.json", root / "layout.json"
            spec_dir, output = root / "specs", root / "manifest.json"
            spec_dir.mkdir()
            self.write(state_path, state); self.write(outline_path, outline); self.write(layout_path, layout); self.write(spec_dir / "S01-r001.json", spec())
            base = dict(state=state_path, spec_dir=spec_dir, approved_outline=outline_path, layout_requirements=layout_path, output_ratio="16:9", manifest_output=output, artifact_id="m", revision=1, previous_manifest=None, timestamp_utc=NOW)
            for changed in ([], ["S99"], ["S01", "S01"]):
                with self.subTest(changed=changed):
                    before = state_path.read_bytes()
                    with self.assertRaises(ContractError):
                        _accept(SimpleNamespace(**base, changed_slide_id=changed))
                    self.assertEqual(state_path.read_bytes(), before)
                    self.assertFalse(output.exists())
            next_state, _ = _accept(SimpleNamespace(**base, changed_slide_id=["S01"]))
            self.assertEqual(next_state["changed_slide_ids"], [])

    def test_projection_bundle_binds_actual_manifest_and_slide_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            slides, manifest = build_projection(approved(), frozen_at_utc=NOW)
            content_dir = root / "content"; content_dir.mkdir()
            for slide, item in zip(slides, manifest["slides"]):
                self.write(content_dir / item["path"], slide)
            manifest_path = content_dir / "projection-manifest.json"
            self.write(manifest_path, manifest)
            state = initial_state(task_id="t", deck_id="D")
            state["current_artifacts"]["slide_content_manifest_sha256"] = canonical_sha256(manifest)
            _, paths = _projection_bundle(state, content_dir)
            self.assertEqual(set(paths), {"S01"})

            tampered = copy.deepcopy(manifest); tampered["revision"] = 2
            self.write(manifest_path, tampered)
            with self.assertRaises(ContractError):
                _projection_bundle(state, content_dir)

            self.write(manifest_path, manifest)
            slide_path = content_dir / manifest["slides"][0]["path"]
            changed = json.loads(slide_path.read_text(encoding="utf-8")); changed["artifact_id"] = "tampered"
            self.write(slide_path, changed)
            with self.assertRaises(ContractError):
                _projection_bundle(state, content_dir)


if __name__ == "__main__":
    unittest.main()
