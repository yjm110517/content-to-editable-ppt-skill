from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from canonical_artifact import canonical_sha256
from content_plan_state import advance, initial_state
from deterministic_project_slide_content import build_projection, load_parent_hashes, verify_projection, write_projection
from manage_content_plan import _project_content, _save_state
from schema_utils import ContractError


H = "a" * 64
NOW = "2026-08-11T00:00:00Z"


def page(text: str = "Confirmed text") -> dict:
    return {"slide_id": "S01", "order": 1, "role": "content", "purpose": "Explain authority", "key_message": "No rewriting", "title": {"content_ref": "S01-TITLE", "text": "Approved title"}, "content_blocks": [{"content_ref": "S01-C01", "order": 1, "text": text, "source_refs": ["M01-F01"]}], "visual_intent": "text card", "source_refs": ["M01-F01"]}


def approved(revision: int = 1, *, parent: str | None = None, text: str = "Confirmed text") -> dict:
    return {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": f"approved-r{revision}", "deck_id": "D03", "revision": revision, "parent_sha256": parent, "candidate_revision": revision, "candidate_sha256": H, "confirmation_id": f"confirmation-r{revision}", "confirmation_sha256": H, "pages": [page(text)], "approved_at_utc": NOW}


class P1ProjectionTests(unittest.TestCase):
    def test_projection_preserves_exact_text_identity_and_source(self) -> None:
        outline = approved()
        slides, manifest = build_projection(outline, frozen_at_utc=NOW)
        self.assertEqual(slides[0]["title"], outline["pages"][0]["title"])
        self.assertEqual(slides[0]["content_blocks"], outline["pages"][0]["content_blocks"])
        self.assertEqual(manifest["slides"][0]["sha256"], canonical_sha256(slides[0]))
        verify_projection(outline, slides[0])

    def test_any_post_confirmation_text_change_is_rejected(self) -> None:
        outline = approved()
        slides, _ = build_projection(outline, frozen_at_utc=NOW)
        changed = copy.deepcopy(slides[0])
        changed["content_blocks"][0]["text"] = "Rewritten text"
        with self.assertRaises(ContractError):
            verify_projection(outline, changed)

    def test_projection_refuses_to_overwrite_a_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            slides, manifest = build_projection(approved(), frozen_at_utc=NOW)
            write_projection(target, slides, manifest)
            with self.assertRaises(FileExistsError):
                write_projection(target, slides, manifest)

    def test_new_approved_revision_binds_parent_slide_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent_dir = Path(temp) / "r1"
            slides, manifest = build_projection(approved(), frozen_at_utc=NOW)
            write_projection(parent_dir, slides, manifest)
            parent_hashes = load_parent_hashes(parent_dir)
            outline2 = approved(2, parent=canonical_sha256(approved()), text="User-confirmed revision")
            revised, _ = build_projection(outline2, frozen_at_utc=NOW, parent_hashes=parent_hashes)
            self.assertEqual(revised[0]["parent_sha256"], canonical_sha256(slides[0]))

    def test_managed_projection_finishes_p1_without_agent_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outline = approved()
            outline_path, state_path, output_dir = root / "approved.json", root / "state.json", root / "slides"
            outline_path.write_text(__import__("json").dumps(outline), encoding="utf-8")
            state = initial_state(task_id="t", deck_id="D03")
            events = [
                ("start_routing", {}), ("route_content_to_ppt", {}), ("materials_ready", {}),
                ("initial_candidate_ready", {}), ("request_outline_confirmation", {}),
                ("outline_confirmed", {"artifact_kind": "confirmation", "artifact_sha256": H, "user_evidence_sha256": H}),
                ("approved_outline_recorded", {"artifact_kind": "approved_outline", "artifact_sha256": canonical_sha256(outline)}),
            ]
            for event, kwargs in events:
                state = advance(state, event=event, timestamp_utc=NOW, **kwargs)
            _save_state(state_path, state)
            completed, manifest = _project_content(state_path, outline_path, output_dir, None, NOW)
            self.assertEqual(completed["state"], "p1_complete")
            self.assertEqual(completed["counters"]["planner_calls"], 0)
            self.assertEqual(completed["counters"]["reviewer_calls"], 0)
            self.assertEqual(completed["current_artifacts"]["slide_content_manifest_sha256"], canonical_sha256(manifest))


if __name__ == "__main__":
    unittest.main()
