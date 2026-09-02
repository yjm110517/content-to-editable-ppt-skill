from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
SCHEMAS = ROOT / "content-to-editable-ppt" / "schemas"
sys.path.insert(0, str(SCRIPTS))

from schema_utils import ContractError, validate_schema, validate_semantics
from visual_first_planner import (
    canonicalize_plan_for_runtime,
    content_authority_from_handoff,
    validate_block_against_handoff,
    validate_content_projection,
    validate_plan_against_handoff,
)


def handoff() -> dict:
    return {
        "schema_version": "1.0",
        "deck_id": "deck-01",
        "slide_id": "S01",
        "order": 1,
        "provenance": {
            "stage1_authority_sha256": "0" * 64,
            "stage2_handoff_sha256": "1" * 64,
            "approved_design_sha256": "2" * 64,
            "wireframe_sha256": "3" * 64,
            "visual_spec_sha256": "4" * 64,
        },
        "page": {"section": "", "role": "overview", "key_message": "AI 学习闭环", "source_refs": [], "visual_need": "cards", "wireframe": "wireframe.md"},
        "content": {"text_items": [
            {"id": "title-content", "role": "title", "text": "AI 学习闭环"},
            {"id": "card-01-title-content", "role": "card_title", "text": "提出问题"},
            {"id": "card-01-body-content", "role": "body", "text": "学生根据学习任务提出问题"},
            {"id": "card-02-title-content", "role": "card_title", "text": "分析与反馈"},
            {"id": "card-02-body-content", "role": "body", "text": "系统结合学习情境生成针对性反馈"},
        ]},
        "semantic_structure": {
            "objects": [
                {"id": "title-object", "kind": "text", "role": "title", "content_ref": "title-content"},
                {"id": "card-01", "kind": "shape", "role": "card"},
                {"id": "card-01-title-object", "kind": "text", "role": "card_title", "content_ref": "card-01-title-content"},
                {"id": "card-01-body-object", "kind": "text", "role": "body", "content_ref": "card-01-body-content"},
                {"id": "card-02", "kind": "shape", "role": "card"},
                {"id": "card-02-title-object", "kind": "text", "role": "card_title", "content_ref": "card-02-title-content"},
                {"id": "card-02-body-object", "kind": "text", "role": "body", "content_ref": "card-02-body-content"},
                {"id": "connector-01", "kind": "connector", "role": "flow", "relation_ref": "relation-01"},
            ],
            "regions": [{"id": "main", "role": "main", "members": ["card-01", "card-01-title-object", "card-01-body-object", "card-02", "card-02-title-object", "card-02-body-object"]}],
            "reading_order": ["title-object", "card-01", "card-01-title-object", "card-01-body-object", "card-02", "card-02-title-object", "card-02-body-object"],
            "relations": [{"id": "relation-01", "kind": "sequence", "from_id": "card-01", "to_id": "card-02"}],
        },
        "structured_data": [],
        "stage2": {
            "approved_design": "source.png",
            "visual_spec": "visual-spec.json",
            "visual_objects": [{
                "id": "visual-hero-01", "role": "hero", "description": "右侧无文字复杂插画",
                "handling": {"independent_crop": True, "independent_positioning": True, "z_order_sensitive": True},
                "overlaps_with": [],
            }],
        },
    }


def geometry(x: float, y: float, width: float, height: float) -> dict:
    return {"coordinate_space": "normalized", "x": x, "y": y, "width": width, "height": height}


def shape(element_id: str, x: float, y: float) -> dict:
    return {"id": element_id, "role": "shape", "representation": "native_shape", "geometry": geometry(x, y, 0.2, 0.15), "z_index": 1, "style": {"shape": "roundRect", "fill": {"color": "#DDEEFF"}}}


def text(element_id: str, content_ref: str, x: float, y: float, width: float, height: float, size: int) -> dict:
    return {"id": element_id, "role": "text", "representation": "native_text", "geometry": geometry(x, y, width, height), "z_index": 2, "content_ref": content_ref, "style": {"font_face": "Microsoft YaHei", "font_size_pt": size, "color": "#111111"}}


def plan() -> dict:
    return {
        "schema_version": "1.0",
        "page": {"id": "S01", "iteration": 1},
        "source": {"approved_design": "source.png"},
        "slide": {"width_in": 13.333, "height_in": 7.5, "background": "#FFFFFF"},
        "elements": [
            text("title-object", "title-content", 0.05, 0.05, 0.9, 0.1, 28),
            shape("card-01", 0.08, 0.25),
            text("card-01-title-object", "card-01-title-content", 0.1, 0.27, 0.16, 0.04, 18),
            text("card-01-body-object", "card-01-body-content", 0.1, 0.33, 0.16, 0.08, 13),
            shape("card-02", 0.36, 0.25),
            text("card-02-title-object", "card-02-title-content", 0.38, 0.27, 0.16, 0.04, 18),
            text("card-02-body-object", "card-02-body-content", 0.38, 0.33, 0.16, 0.08, 13),
            {"id": "connector-01", "role": "flow", "representation": "native_connector", "geometry": geometry(0.28, 0.3, 0.08, 0.01), "z_index": 0, "from_id": "card-01", "to_id": "card-02", "style": {"line": {"color": "#335577", "width_pt": 2, "end_arrow": "triangle"}}},
            {"id": "visual-hero-01", "role": "hero", "representation": "raster_asset", "geometry": geometry(0.7, 0.2, 0.2, 0.4), "z_index": 3, "asset_request": {"source": "approved_design", "source_region": geometry(0.7, 0.2, 0.2, 0.4), "contains_text": False}},
        ],
    }


def request() -> dict:
    return {"output_ratio": "16:9", "source_image": "source.png"}


class VisualFirstPlannerTests(unittest.TestCase):
    def test_valid_plan_covers_stage1_and_required_stage2_objects(self) -> None:
        validate_plan_against_handoff(plan(), handoff(), request(), iteration=1, slide_id="S01")

    def test_connector_endpoints_are_owned_by_stage1_relation(self) -> None:
        for mutation in ("wrong_target", "reverse", "missing"):
            with self.subTest(mutation=mutation):
                candidate = plan()
                connector = next(item for item in candidate["elements"] if item["id"] == "connector-01")
                if mutation == "wrong_target":
                    connector["to_id"] = "visual-hero-01"
                elif mutation == "reverse":
                    connector["from_id"], connector["to_id"] = connector["to_id"], connector["from_id"]
                else:
                    candidate["elements"].remove(connector)
                with self.assertRaises(ContractError) as raised:
                    validate_plan_against_handoff(candidate, handoff(), request(), iteration=1, slide_id="S01")
                self.assertTrue(
                    {"topology_mismatch", "grounding_incomplete"} & {item["code"] for item in raised.exception.errors}
                )

    def test_stage1_stable_ids_and_content_refs_are_authoritative(self) -> None:
        candidates = []
        renamed = plan()
        renamed["elements"][0]["id"] = "renamed-title"
        candidates.append(renamed)
        missing_card = plan()
        missing_card["elements"] = [item for item in missing_card["elements"] if item["id"] != "card-01"]
        candidates.append(missing_card)
        wrong_content = plan()
        wrong_content["elements"][0]["content_ref"] = "card-01-title-content"
        candidates.append(wrong_content)
        for candidate in candidates:
            with self.subTest(candidate=candidate["elements"][0]["id"]):
                with self.assertRaises(ContractError) as raised:
                    validate_plan_against_handoff(candidate, handoff(), request(), iteration=1, slide_id="S01")
                self.assertTrue(
                    {"grounding_incomplete", "content_identity"} & {item["code"] for item in raised.exception.errors}
                )

    def test_required_visual_object_cannot_be_omitted(self) -> None:
        candidate = plan()
        candidate["elements"] = [item for item in candidate["elements"] if item["id"] != "visual-hero-01"]
        with self.assertRaises(ContractError) as raised:
            validate_plan_against_handoff(candidate, handoff(), request(), iteration=1, slide_id="S01")
        self.assertIn("grounding_incomplete", {item["code"] for item in raised.exception.errors})

    def test_chart_requires_p4_instead_of_raster_fallback(self) -> None:
        current = handoff()
        current["semantic_structure"]["objects"].append({"id": "chart-01", "kind": "chart", "role": "evidence", "data_ref": "data-01"})
        with self.assertRaises(ContractError) as raised:
            validate_plan_against_handoff(plan(), current, request(), iteration=1, slide_id="S01")
        self.assertIn("unsupported_reconstruction", {item["code"] for item in raised.exception.errors})

    def test_candidate_ratio_precision_is_accepted_and_runtime_size_is_canonical(self) -> None:
        candidate = plan()
        candidate["slide"]["width_in"] = 13.333333
        original = copy.deepcopy(candidate)
        validate_plan_against_handoff(candidate, handoff(), request(), iteration=1, slide_id="S01")
        canonical = canonicalize_plan_for_runtime(candidate, request())
        self.assertEqual(original, candidate)
        self.assertEqual(13.333, canonical["slide"]["width_in"])
        self.assertEqual(7.5, canonical["slide"]["height_in"])

    def test_candidate_rejects_material_slide_ratio_errors(self) -> None:
        for width, height in ((12, 7.5), (10, 10), (13.333, 8)):
            with self.subTest(width=width, height=height):
                candidate = plan()
                candidate["slide"].update({"width_in": width, "height_in": height})
                with self.assertRaises(ContractError) as raised:
                    validate_plan_against_handoff(candidate, handoff(), request(), iteration=1, slide_id="S01")
                self.assertIn("slide_ratio_mismatch", {item["code"] for item in raised.exception.errors})

    def test_content_projection_is_semantic_not_byte_based(self) -> None:
        current = handoff()
        projection = content_authority_from_handoff(current)
        validate_content_projection(current, copy.deepcopy(projection))
        projection["text_items"][0]["text"] = "changed"
        with self.assertRaises(ContractError) as raised:
            validate_content_projection(current, projection)
        self.assertEqual("content_projection_mismatch", raised.exception.errors[0]["code"])

    def test_object_scoped_block_rejects_unknown_ids(self) -> None:
        with self.assertRaises(ContractError) as raised:
            validate_block_against_handoff({"scope": "objects", "object_ids": ["missing"]}, handoff())
        self.assertEqual("unknown_reference", raised.exception.errors[0]["code"])

    def test_planner_response_plan_block_and_revision_contracts(self) -> None:
        plan_response = {"schema_version": "1.4", "task_id": "task", "iteration": 1, "mode": "initial", "outcome": "plan", "artifacts": {"reconstruction_plan": plan()}}
        validate_schema("planner_response", plan_response, SCHEMAS)
        validate_semantics("planner_response", plan_response)

        page_block = {"schema_version": "1.4", "task_id": "task", "iteration": 1, "mode": "initial", "outcome": "block", "block": {"code": "authority_conflict", "scope": "page", "message": "page-wide conflict"}}
        validate_schema("planner_response", page_block, SCHEMAS)
        invalid_page = copy.deepcopy(page_block)
        invalid_page["block"]["object_ids"] = ["card-01"]
        with self.assertRaises(ContractError):
            validate_schema("planner_response", invalid_page, SCHEMAS)

        object_block = copy.deepcopy(page_block)
        object_block["block"] = {"code": "unsafe_crop", "scope": "objects", "object_ids": ["visual-hero-01"], "message": "unsafe crop"}
        validate_schema("planner_response", object_block, SCHEMAS)
        missing_ids = copy.deepcopy(object_block)
        del missing_ids["block"]["object_ids"]
        with self.assertRaises(ContractError):
            validate_schema("planner_response", missing_ids, SCHEMAS)

        revision = {"schema_version": "1.4", "task_id": "task", "iteration": 1, "mode": "revision", "artifacts": {"review_patch": {}}}
        validate_schema("planner_response", revision, SCHEMAS)

    def test_planner_response_rejects_mixed_unknown_and_legacy_shapes(self) -> None:
        valid = {"schema_version": "1.4", "task_id": "task", "iteration": 1, "mode": "initial", "outcome": "plan", "artifacts": {"reconstruction_plan": plan()}}
        invalid = []
        both = copy.deepcopy(valid)
        both["block"] = {"code": "authority_conflict", "scope": "page", "message": "conflict"}
        invalid.append(both)
        block_with_plan = copy.deepcopy(valid)
        block_with_plan["outcome"] = "block"
        block_with_plan["block"] = {"code": "authority_conflict", "scope": "page", "message": "conflict"}
        invalid.append(block_with_plan)
        unknown_outcome = copy.deepcopy(valid)
        unknown_outcome["outcome"] = "unknown"
        invalid.append(unknown_outcome)
        unknown_code = {"schema_version": "1.4", "task_id": "task", "iteration": 1, "mode": "initial", "outcome": "block", "block": {"code": "unknown", "scope": "page", "message": "unknown"}}
        invalid.append(unknown_code)
        for legacy_key in ("layout", "crops", "asset_manifest", "representation_decisions", "generated_assets"):
            legacy = copy.deepcopy(valid)
            legacy["artifacts"][legacy_key] = {}
            invalid.append(legacy)
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ContractError):
                    validate_schema("planner_response", candidate, SCHEMAS)


if __name__ == "__main__":
    unittest.main()
