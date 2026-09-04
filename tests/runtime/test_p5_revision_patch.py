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
from schema_utils import ContractError, validate_schema, validate_semantics
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
    def test_revision_patch_semantic_version_is_registered(self) -> None:
        validate_semantics("revision_patch", patch())

    def test_linked_connector_requires_actual_target_geometry_change(self) -> None:
        current, candidate = plan(), patch()
        candidate["operations"][0].update(path="/z_index", value=99)
        with self.assertRaises(ContractError):
            self._validate(current, candidate)

    def test_revision_prompts_are_contract_specific(self) -> None:
        from agent_common import load_role
        _, _, canonical, _ = load_role("planner", SCHEMAS, mode="revision_canonical")
        _, _, legacy, _ = load_role("planner", SCHEMAS, mode="revision")
        self.assertNotEqual(canonical, legacy)
        self.assertIn("artifacts.review_patch", legacy.read_text(encoding="utf-8"))

    def test_scope_issue_and_linked_negative_matrix(self) -> None:
        cases = {
            "unknown-target": lambda p: p.update(targets=["unknown"]),
            "duplicate-target": lambda p: p["targets"].append("card-02"),
            "unknown-linked": lambda p: p["linked_elements"][0].update(element_id="unknown"),
            "duplicate-linked": lambda p: p["linked_elements"].append({"element_id": "connector-01", "reason": "another reason"}),
            "target-linked-overlap": lambda p: p["targets"].append("connector-01"),
            "blank-reason": lambda p: p["linked_elements"][0].update(reason="   "),
            "non-connector": lambda p: p["linked_elements"][0].update(element_id="card-01"),
            "unknown-issue": lambda p: p["operations"][0].update(issue_id="unknown"),
            "approved-target": lambda p: p["targets"].append("title-object"),
            "empty": lambda p: p.update(operations=[]),
            "undeclared-target-operation": lambda p: p["operations"][0].update(element_id="card-01"),
        }
        for name, change in cases.items():
            with self.subTest(name=name):
                candidate = patch()
                change(candidate)
                with self.assertRaises(ContractError):
                    self._validate(plan(), candidate)

    def test_issue_must_be_recoverable_non_suggestion_and_directly_reference_target(self) -> None:
        for changes in ({"recoverability": "irrecoverable"}, {"severity": "suggestion"}, {"element_ids": ["card-01"]}):
            with self.subTest(changes=changes):
                r = review()
                r["issues"][0].update(changes)
                candidate = patch()
                candidate["based_on_review_sha256"] = digest(r)
                with self.assertRaises(ContractError):
                    validate_patch(candidate, plan(), handoff(), r, evaluation(), task_id="task-01", base_sha256=digest(plan()), review_sha256=digest(r), evaluation_sha256=digest(evaluation()))

    def test_all_authority_and_arbitrary_paths_are_rejected(self) -> None:
        paths = ["/id", "/role", "/representation", "/content_ref", "/data_ref", "/from_id", "/to_id", "/text", "/data", "/style/chart_type",
                 "/geometry/coordinate_space", "/asset_request/source", "/asset_request/contains_text", "/style", "/", "/style/unknown", "/style/color_tokens/0"]
        for path in paths:
            with self.subTest(path=path):
                candidate = patch()
                candidate["operations"][0].update(path=path, value="unauthorized")
                with self.assertRaises(ContractError):
                    self._validate(plan(), candidate)

    def test_schema_declared_style_paths_match_allowlist(self) -> None:
        import json
        from revision_patch import STYLE_PATHS
        schema = json.loads((SCHEMAS / "reconstruction-plan.schema.json").read_text(encoding="utf-8"))
        def leaves(node, prefix):
            if "$ref" in node:
                node = schema["$defs"][node["$ref"].split("/")[-1]]
            if "properties" in node:
                return {p for name, child in node["properties"].items() for p in leaves(child, f"{prefix}/{name}")}
            return {prefix}
        for representation, definition in (("native_text", "textStyle"), ("native_shape", "shapeStyle"), ("native_connector", "connectorStyle"), ("native_chart", "chartStyle"), ("native_table", "tableStyle")):
            self.assertEqual(leaves(schema["$defs"][definition], "/style") - {"/style/chart_type"}, STYLE_PATHS[representation])

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
