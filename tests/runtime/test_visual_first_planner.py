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
        "page": {"section": "", "role": "overview", "key_message": "Flow", "source_refs": [], "visual_need": "cards", "wireframe": "wireframe.md"},
        "content": {"text_items": [{"id": "title-content", "role": "title", "text": "Canonical Plan"}]},
        "semantic_structure": {
            "objects": [
                {"id": "title-object", "kind": "text", "role": "title", "content_ref": "title-content"},
                {"id": "card-01", "kind": "shape", "role": "card"},
                {"id": "card-02", "kind": "shape", "role": "card"},
                {"id": "connector-01", "kind": "connector", "role": "flow", "relation_ref": "relation-01"},
                {"id": "visual-slot", "kind": "visual_placeholder", "role": "supporting_visual"},
            ],
            "regions": [{"id": "main", "role": "main", "members": ["card-01", "card-02"]}],
            "reading_order": ["title-object", "card-01", "card-02", "visual-slot"],
            "relations": [{"id": "relation-01", "kind": "sequence", "from_id": "card-01", "to_id": "card-02"}],
        },
        "structured_data": [],
        "stage2": {
            "approved_design": "source.png",
            "visual_spec": "visual-spec.json",
            "visual_objects": [{
                "id": "visual-hero", "role": "hero", "description": "abstract visual",
                "handling": {"independent_crop": True, "independent_positioning": True, "z_order_sensitive": True},
                "overlaps_with": [],
            }],
        },
    }


def geometry(x: float, y: float, width: float, height: float) -> dict:
    return {"coordinate_space": "normalized", "x": x, "y": y, "width": width, "height": height}


def shape(element_id: str, x: float, y: float) -> dict:
    return {"id": element_id, "role": "shape", "representation": "native_shape", "geometry": geometry(x, y, 0.2, 0.15), "z_index": 1, "style": {"shape": "roundRect", "fill": {"color": "#DDEEFF"}}}


def plan() -> dict:
    return {
        "schema_version": "1.0",
        "page": {"id": "S01", "iteration": 1},
        "source": {"approved_design": "source.png"},
        "slide": {"width_in": 13.333, "height_in": 7.5, "background": "#FFFFFF"},
        "elements": [
            {"id": "title-object", "role": "title", "representation": "native_text", "geometry": geometry(0.05, 0.05, 0.9, 0.1), "z_index": 2, "content_ref": "title-content", "style": {"font_face": "Microsoft YaHei", "font_size_pt": 28, "color": "#111111"}},
            shape("card-01", 0.1, 0.25),
            shape("card-02", 0.4, 0.25),
            {"id": "connector-01", "role": "flow", "representation": "native_connector", "geometry": geometry(0.3, 0.3, 0.1, 0.01), "z_index": 0, "from_id": "card-01", "to_id": "card-02", "style": {"line": {"color": "#335577", "width_pt": 2, "end_arrow": "triangle"}}},
            shape("visual-slot", 0.68, 0.2),
            shape("visual-hero", 0.7, 0.5),
        ],
    }


def request() -> dict:
    return {"output_ratio": "16:9", "source_image": "source.png"}


class VisualFirstPlannerTests(unittest.TestCase):
    def test_valid_plan_covers_stage1_and_required_stage2_objects(self) -> None:
        validate_plan_against_handoff(plan(), handoff(), request(), iteration=1, slide_id="S01")

    def test_connector_endpoints_are_owned_by_stage1_relation(self) -> None:
        candidate = plan()
        candidate["elements"][3]["to_id"] = "visual-hero"
        with self.assertRaises(ContractError) as raised:
            validate_plan_against_handoff(candidate, handoff(), request(), iteration=1, slide_id="S01")
        self.assertIn("topology_mismatch", {item["code"] for item in raised.exception.errors})

    def test_required_visual_object_cannot_be_omitted(self) -> None:
        candidate = plan()
        candidate["elements"] = [item for item in candidate["elements"] if item["id"] != "visual-hero"]
        with self.assertRaises(ContractError) as raised:
            validate_plan_against_handoff(candidate, handoff(), request(), iteration=1, slide_id="S01")
        self.assertIn("grounding_incomplete", {item["code"] for item in raised.exception.errors})

    def test_chart_requires_p4_instead_of_raster_fallback(self) -> None:
        current = handoff()
        current["semantic_structure"]["objects"].append({"id": "chart-01", "kind": "chart", "role": "evidence", "data_ref": "data-01"})
        with self.assertRaises(ContractError) as raised:
            validate_plan_against_handoff(plan(), current, request(), iteration=1, slide_id="S01")
        self.assertIn("unsupported_reconstruction", {item["code"] for item in raised.exception.errors})

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
        object_block["block"] = {"code": "unsafe_crop", "scope": "objects", "object_ids": ["visual-hero"], "message": "unsafe crop"}
        validate_schema("planner_response", object_block, SCHEMAS)
        missing_ids = copy.deepcopy(object_block)
        del missing_ids["block"]["object_ids"]
        with self.assertRaises(ContractError):
            validate_schema("planner_response", missing_ids, SCHEMAS)

        revision = {"schema_version": "1.4", "task_id": "task", "iteration": 1, "mode": "revision", "artifacts": {"review_patch": {}}}
        validate_schema("planner_response", revision, SCHEMAS)


if __name__ == "__main__":
    unittest.main()
