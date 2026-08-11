from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from canonical_artifact import canonical_sha256
from content_plan_rules import validate_candidate_outline, validate_outline_confirmation
from content_plan_state import advance, initial_state
from manage_content_plan import _record_response, _request_confirmation, _save_state, _submit_candidate, write_json
from render_outline_preview import render
from schema_utils import ContractError


SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"
H = "a" * 64
NOW = "2026-08-11T00:00:00Z"


def deck_request() -> dict:
    return {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "task_id": "t", "deck_id": "D03", "topic": "Planning", "objective": "Explain planning", "audience": "developers", "language": "zh-CN", "page_count": 1, "output_ratio": "16:9", "source_material_ids": ["M01"], "must_preserve": [], "prohibited_changes": [], "visual_requirements": [], "external_research": "not_authorized"}


def materials() -> dict:
    return {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "materials-r1", "deck_id": "D03", "revision": 1, "parent_sha256": None, "external_research": "not_authorized", "status": "ready", "materials": [{"material_id": "M01", "display_name": "brief", "media_type": "text/plain", "read_status": "readable", "required_for_task": True, "blocking": False, "content_sha256": H, "reason": None}], "facts": [{"fact_id": "M01-F01", "text": "Confirmed text is authoritative", "kind": "fact", "source_refs": ["M01"]}], "warnings": [], "ignore_authorizations": [], "created_at_utc": NOW}


def candidate(revision: int = 1, *, parent: str | None = None, user_hash: str | None = None) -> dict:
    document = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": f"candidate-r{revision}", "deck_id": "D03", "revision": revision, "parent_sha256": parent, "material_understanding_sha256": canonical_sha256(materials()), "host_pass_counts": {"planning": 1, "revision": revision - 1, "automatic_regeneration": 0}, "pages": [{"slide_id": "S01", "order": 1, "role": "cover", "purpose": "Open the deck", "key_message": "Authority", "title": {"content_ref": "S01-TITLE", "text": "Content planning"}, "content_blocks": [{"content_ref": "S01-C01", "order": 1, "text": "Confirmed text is authoritative", "source_refs": ["M01-F01"]}], "visual_intent": "hero", "source_refs": ["M01-F01"]}], "created_at_utc": NOW}
    if user_hash:
        document["user_revision_request_sha256"] = user_hash
    return document


def confirmation(candidate_document: dict, status: str, user_hash: str = H) -> dict:
    return {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "confirmation_id": f"confirmation-r{candidate_document['revision']}-{status}", "deck_id": "D03", "candidate_revision": candidate_document["revision"], "candidate_sha256": canonical_sha256(candidate_document), "status": status, "user_message_sha256": user_hash, "created_at_utc": NOW}


class P1OutlineConfirmationTests(unittest.TestCase):
    def test_candidate_enforces_page_count_sources_and_content_identity(self) -> None:
        valid = candidate()
        validate_candidate_outline(valid, deck_request=deck_request(), materials=materials(), schema_dir=SCHEMA_DIR)
        duplicate = copy.deepcopy(valid)
        duplicate["pages"][0]["content_blocks"][0]["content_ref"] = "S01-TITLE"
        with self.assertRaises(ContractError):
            validate_candidate_outline(duplicate, deck_request=deck_request(), materials=materials(), schema_dir=SCHEMA_DIR)
        unknown = copy.deepcopy(valid)
        unknown["pages"][0]["content_blocks"][0]["source_refs"] = ["UNKNOWN"]
        with self.assertRaises(ContractError):
            validate_candidate_outline(unknown, deck_request=deck_request(), materials=materials(), schema_dir=SCHEMA_DIR)

    def test_stale_confirmation_cannot_approve_modified_candidate(self) -> None:
        original = candidate()
        response = confirmation(original, "confirmed")
        modified = copy.deepcopy(original)
        modified["pages"][0]["title"]["text"] = "Changed"
        with self.assertRaises(ContractError):
            validate_outline_confirmation(modified, response, SCHEMA_DIR)

    def test_user_revision_then_confirmation_promotes_exact_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state_path, request_path, materials_path = root / "state.json", root / "request.json", root / "materials.json"
            first_path, changed_response_path = root / "candidate-r1.json", root / "changes.json"
            revised_path, confirmed_path, approved_path = root / "candidate-r2.json", root / "confirmed.json", root / "approved.json"
            write_json(request_path, deck_request()); write_json(materials_path, materials()); write_json(first_path, candidate())
            state = initial_state(task_id="t", deck_id="D03")
            for event in ("start_routing", "route_content_to_ppt", "materials_ready"):
                state = advance(state, event=event, timestamp_utc=NOW)
            _save_state(state_path, state)
            _submit_candidate(state_path, first_path, request_path, materials_path)
            _request_confirmation(state_path)
            write_json(changed_response_path, confirmation(candidate(), "changes_requested"))
            _record_response(state_path, first_path, changed_response_path, None, 1, None)

            revised = candidate(2, parent=canonical_sha256(candidate()), user_hash=H)
            revised["pages"][0]["title"]["text"] = "Revised content planning"
            write_json(revised_path, revised)
            _submit_candidate(state_path, revised_path, request_path, materials_path)
            _request_confirmation(state_path)
            write_json(confirmed_path, confirmation(revised, "confirmed"))
            state, approved = _record_response(state_path, revised_path, confirmed_path, approved_path, 1, None)
            self.assertEqual(approved["pages"], revised["pages"])
            self.assertEqual(state["state"], "outline_approved")
            self.assertEqual(state["counters"], {"host_planning_pass_count": 1, "host_revision_pass_count": 1, "automatic_regeneration_count": 0, "planner_calls": 0, "reviewer_calls": 0})

    def test_preview_is_deterministic_and_marks_exact_text(self) -> None:
        first = render(candidate())
        self.assertEqual(first, render(candidate()))
        self.assertIn("Final page text", first)
        self.assertIn("[S01-C01] Confirmed text is authoritative", first)


if __name__ == "__main__":
    unittest.main()
