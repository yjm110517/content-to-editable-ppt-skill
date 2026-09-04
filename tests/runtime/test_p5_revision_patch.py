from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
SCHEMAS = ROOT / "content-to-editable-ppt" / "schemas"
sys.path.insert(0, str(SCRIPTS))

from revision_patch import apply_patch, validate_patch
from schema_utils import ContractError, validate_schema
from tests.runtime.test_visual_first_planner import handoff, plan


def digest(value: object) -> str:
    return hashlib.sha256(repr(value).encode()).hexdigest()


def review() -> dict:
    return {"issues": [{"id": "issue-01", "severity": "major", "recoverability": "recoverable", "element_ids": ["card-02"], "asset_ids": []}], "approved_elements": ["title-object", "card-01", "visual-hero-01"]}


def evaluation() -> dict:
    return {"policy_decision": "revise"}


def patch(base: dict | None = None) -> dict:
    current = base or plan()
    return {"schema_version": "1.0", "task_id": "task-01", "page_id": "S01", "from_iteration": 1, "to_iteration": 2, "base_plan_sha256": digest(current), "based_on_review_sha256": digest(review()), "based_on_review_evaluation_sha256": digest(evaluation()), "targets": ["card-02"], "linked_elements": [{"element_id": "connector-01", "reason": "card-02 movement requires its incoming connector geometry to align"}], "operations": [{"issue_id": "issue-01", "element_id": "card-02", "path": "/geometry/y", "value": 0.20}, {"issue_id": "issue-01", "element_id": "connector-01", "path": "/geometry/width", "value": 0.06}], "revision_reason": "move card upward"}


class P5RevisionPatchTests(unittest.TestCase):
    def _validate(self, current: dict, candidate: dict) -> None:
        validate_schema("revision_patch", candidate, SCHEMAS)
        validate_patch(candidate, current, handoff(), review(), evaluation(), task_id="task-01", base_sha256=digest(current), review_sha256=digest(review()), evaluation_sha256=digest(evaluation()))

    def test_scoped_patch_updates_only_target_and_direct_connector(self) -> None:
        current, candidate = plan(), patch()
        self._validate(current, candidate)
        result, diff = apply_patch(current, candidate, handoff_sha256="a" * 64, approved_design_sha256="b" * 64, patch_sha256="c" * 64)
        self.assertEqual("1.2", result["schema_version"])
        self.assertEqual(2, result["page"]["iteration"])
        self.assertEqual(0.20, next(item for item in result["elements"] if item["id"] == "card-02")["geometry"]["y"])
        self.assertEqual(["title-object", "card-01", "card-01-title-object", "card-01-body-object", "card-02-title-object", "card-02-body-object", "visual-hero-01"], diff["unchanged_elements"])
        validate_schema("reconstruction_plan", result, SCHEMAS)

    def test_locked_and_immutable_changes_are_rejected(self) -> None:
        for element_id, path, value in (("title-object", "/geometry/y", 0.02), ("card-02", "/representation", "raster_asset"), ("connector-01", "/from_id", "card-02"), ("card-02", "/content_ref", "x")):
            with self.subTest(path=path):
                current, candidate = plan(), patch()
                candidate["operations"][0] = {"issue_id": "issue-01", "element_id": element_id, "path": path, "value": value}
                if element_id != "card-02":
                    candidate["targets"] = [element_id]
                candidate["base_plan_sha256"] = digest(current)
                with self.assertRaises(ContractError):
                    self._validate(current, candidate)

    def test_raster_region_is_allowed_but_pixel_crop_is_not(self) -> None:
        current = plan()
        candidate = patch(current)
        candidate["targets"] = ["visual-hero-01"]
        candidate["linked_elements"] = []
        candidate["operations"] = [{"issue_id": "issue-02", "element_id": "visual-hero-01", "path": "/asset_request/source_region/x", "value": 0.65}]
        source_review = review()
        source_review["approved_elements"].remove("visual-hero-01")
        source_review["issues"].append({"id": "issue-02", "severity": "major", "recoverability": "recoverable", "element_ids": ["visual-hero-01"], "asset_ids": []})
        candidate["based_on_review_sha256"] = digest(source_review)
        validate_patch(candidate, current, handoff(), source_review, evaluation(), task_id="task-01", base_sha256=digest(current), review_sha256=digest(source_review), evaluation_sha256=digest(evaluation()))
        candidate["operations"][0]["path"] = "/asset_request/source_region/box_px"
        with self.assertRaises(ContractError):
            validate_patch(candidate, current, handoff(), source_review, evaluation(), task_id="task-01", base_sha256=digest(current), review_sha256=digest(source_review), evaluation_sha256=digest(evaluation()))

    def test_duplicate_and_noop_operations_are_rejected(self) -> None:
        current, candidate = plan(), patch()
        candidate["operations"].append(copy.deepcopy(candidate["operations"][0]))
        with self.assertRaises(ContractError):
            self._validate(current, candidate)
        candidate = patch(current)
        candidate["operations"][0]["value"] = 0.25
        with self.assertRaises(ContractError):
            self._validate(current, candidate)


if __name__ == "__main__":
    unittest.main()
