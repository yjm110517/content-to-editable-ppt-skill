from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from canonical_artifact import canonical_sha256
from content_plan_rules import validate_material_understanding, validate_task_route
from manage_content_plan import _materials, _route, _save_state
from content_plan_state import initial_state
from schema_utils import ContractError


SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"
HASH = "a" * 64
NOW = "2026-08-11T00:00:00Z"


def route(route_name: str, revision: int = 1) -> dict:
    value = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "task_id": "t", "route_id": f"r{revision}", "revision": revision, "parent_route_sha256": None if revision == 1 else HASH, "route": route_name, "intent_summary": "test route", "evidence": ["user request"], "created_at_utc": NOW}
    if revision > 1:
        value["clarification_message_sha256"] = HASH
    return value


def material(*, required: bool, status: str, blocking: bool) -> dict:
    return {"material_id": "M01", "display_name": "brief", "media_type": "application/pdf", "read_status": status, "required_for_task": required, "blocking": blocking, "content_sha256": HASH if status == "readable" else None, "reason": None if status == "readable" else "cannot extract text"}


def materials(item: dict, *, status: str, warnings: list[str] | None = None, authorizations: list[dict] | None = None) -> dict:
    return {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "materials-r1", "deck_id": "D03", "revision": 1, "parent_sha256": None, "external_research": "not_authorized", "status": status, "materials": [item], "facts": [], "warnings": warnings or [], "ignore_authorizations": authorizations or [], "created_at_utc": NOW}


class P1RoutingMaterialTests(unittest.TestCase):
    def test_route_revision_requires_clarification_evidence(self) -> None:
        value = route("content_to_ppt", revision=2)
        del value["clarification_message_sha256"]
        with self.assertRaises(ContractError):
            validate_task_route(value, SCHEMA_DIR)

    def test_route_clarification_then_content_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state_path, route_path = root / "state.json", root / "route.json"
            _save_state(state_path, initial_state(task_id="t", deck_id="D03"))
            route_path.write_text(__import__("json").dumps(route("needs_clarification")), encoding="utf-8")
            state = _route(state_path, route_path)
            self.assertEqual(state["state"], "awaiting_route_clarification")
            route_path.write_text(__import__("json").dumps(route("content_to_ppt", 2)), encoding="utf-8")
            state = _route(state_path, route_path)
            self.assertEqual(state["state"], "material_intake")

    def test_image_route_bypasses_content_planning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state_path, route_path = root / "state.json", root / "route.json"
            _save_state(state_path, initial_state(task_id="t", deck_id="single"))
            route_path.write_text(__import__("json").dumps(route("image_to_editable_ppt")), encoding="utf-8")
            self.assertEqual(_route(state_path, route_path)["state"], "p1_bypassed")

    def test_required_unreadable_material_blocks(self) -> None:
        document = materials(material(required=True, status="unreadable", blocking=True), status="blocked")
        result = validate_material_understanding(document, SCHEMA_DIR)
        self.assertEqual(result["blockers"], ["M01"])

    def test_optional_unreadable_material_warns_and_continues(self) -> None:
        document = materials(material(required=False, status="unreadable", blocking=False), status="ready", warnings=["M01 could not be read"])
        result = validate_material_understanding(document, SCHEMA_DIR)
        self.assertTrue(result["ready"])
        self.assertEqual(result["warnings"], ["M01"])

    def test_authorization_must_bind_current_material_record(self) -> None:
        item = material(required=True, status="unreadable", blocking=False)
        authorization = {"material_id": "M01", "material_record_sha256": canonical_sha256(item), "user_message_sha256": HASH, "authorized_at_utc": NOW}
        document = materials(item, status="ready", warnings=["M01 ignored by user"], authorizations=[authorization])
        self.assertTrue(validate_material_understanding(document, SCHEMA_DIR)["ready"])
        changed = copy.deepcopy(document)
        changed["materials"][0]["reason"] = "different failure"
        with self.assertRaises(ContractError):
            validate_material_understanding(changed, SCHEMA_DIR)

    def test_unapproved_external_source_is_rejected(self) -> None:
        item = material(required=True, status="readable", blocking=False)
        document = materials(item, status="ready")
        document["facts"] = [{"fact_id": "F01", "text": "external claim", "kind": "fact", "source_refs": ["WEB:example"]}]
        with self.assertRaises(ContractError):
            validate_material_understanding(document, SCHEMA_DIR)


if __name__ == "__main__":
    unittest.main()
