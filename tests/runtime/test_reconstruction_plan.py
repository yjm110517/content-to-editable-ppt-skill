from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"
sys.path.insert(0, str(SCRIPTS))

from schema_utils import ContractError, validate_schema, validate_semantics


def valid_plan() -> dict:
    geometry = {"coordinate_space": "normalized", "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.1}
    return {
        "schema_version": "1.0",
        "page": {"id": "slide_01", "iteration": 1},
        "source": {"approved_design": "source.png"},
        "slide": {"width_in": 13.333, "height_in": 7.5, "background": "#FFFFFF"},
        "elements": [{
            "id": "title", "role": "title", "representation": "native_text", "geometry": geometry, "z_index": 10,
            "content_ref": "title", "style": {"font_face": "Aptos", "font_size_pt": 28, "color": "#102040"},
        }],
    }


class ReconstructionPlanContractTests(unittest.TestCase):
    def _validate(self, plan: dict) -> None:
        validate_schema("reconstruction_plan", plan, SCHEMA_DIR)
        validate_semantics("reconstruction_plan", plan)

    def test_minimal_valid_plan_passes(self) -> None:
        self._validate(valid_plan())

    def test_missing_required_top_level_fields_and_empty_elements_fail(self) -> None:
        for field in ("page", "source", "elements"):
            with self.subTest(field=field):
                plan = valid_plan()
                del plan[field]
                with self.assertRaises(ContractError):
                    validate_schema("reconstruction_plan", plan, SCHEMA_DIR)
        plan = valid_plan()
        plan["elements"] = []
        with self.assertRaises(ContractError):
            validate_schema("reconstruction_plan", plan, SCHEMA_DIR)

    def test_request_and_source_metadata_are_forbidden(self) -> None:
        for target, field, value in (("page", "topic", "x"), ("page", "typography_interaction", "default"), ("source", "width_px", 1920)):
            with self.subTest(field=field):
                plan = valid_plan()
                plan[target][field] = value
                with self.assertRaises(ContractError):
                    validate_schema("reconstruction_plan", plan, SCHEMA_DIR)

    def test_duplicate_id_and_out_of_bounds_geometry_fail_semantics(self) -> None:
        plan = valid_plan()
        duplicate = copy.deepcopy(plan["elements"][0])
        duplicate["content_ref"] = "subtitle"
        plan["elements"].append(duplicate)
        plan["elements"][0]["geometry"]["x"] = 0.8
        plan["elements"][0]["geometry"]["width"] = 0.3
        validate_schema("reconstruction_plan", plan, SCHEMA_DIR)
        with self.assertRaises(ContractError) as raised:
            validate_semantics("reconstruction_plan", plan)
        self.assertTrue({"semantic_error", "geometry_out_of_bounds"}.issubset({item["code"] for item in raised.exception.errors}))

    def test_connector_references_are_validated(self) -> None:
        plan = valid_plan()
        plan["elements"].append({
            "id": "line", "role": "connector", "representation": "native_connector",
            "geometry": {"coordinate_space": "normalized", "x": 0.2, "y": 0.3, "width": 0.2, "height": 0.01},
            "z_index": 5, "from_id": "line", "to_id": "missing", "style": {"line": {"color": "#000000", "width_pt": 1}},
        })
        validate_schema("reconstruction_plan", plan, SCHEMA_DIR)
        with self.assertRaises(ContractError) as raised:
            validate_semantics("reconstruction_plan", plan)
        self.assertEqual({"self_reference", "unknown_reference"}, {item["code"] for item in raised.exception.errors})

    def test_known_unsupported_and_unknown_representations_are_distinct(self) -> None:
        known = valid_plan()
        known["elements"] = [{
            "id": "svg", "role": "illustration", "representation": "svg",
            "geometry": {"coordinate_space": "normalized", "x": 0.1, "y": 0.1, "width": 0.4, "height": 0.3}, "z_index": 1,
        }]
        validate_schema("reconstruction_plan", known, SCHEMA_DIR)
        with self.assertRaises(ContractError) as raised:
            validate_semantics("reconstruction_plan", known)
        self.assertEqual("unsupported_representation", raised.exception.errors[0]["code"])

        unknown = copy.deepcopy(known)
        unknown["elements"][0]["representation"] = "foo_bar_xyz"
        with self.assertRaises(ContractError):
            validate_schema("reconstruction_plan", unknown, SCHEMA_DIR)

        missing_data_ref = valid_plan()
        missing_data_ref["schema_version"] = "1.1"
        missing_data_ref["elements"] = [{
            "id": "chart", "role": "chart", "representation": "native_chart",
            "geometry": {"coordinate_space": "normalized", "x": 0.1, "y": 0.1, "width": 0.4, "height": 0.3}, "z_index": 1,
            "style": {"chart_type": "vertical_bar"},
        }]
        with self.assertRaises(ContractError):
            validate_schema("reconstruction_plan", missing_data_ref, SCHEMA_DIR)

    def test_raster_contract_requires_safe_text_free_request(self) -> None:
        plan = valid_plan()
        plan["elements"] = [{
            "id": "hero", "role": "complex_visual", "representation": "raster_asset",
            "geometry": {"coordinate_space": "normalized", "x": 0.6, "y": 0.2, "width": 0.2, "height": 0.4}, "z_index": 1,
            "asset_request": {"source": "approved_design", "source_region": {"coordinate_space": "normalized", "x": 0.5, "y": 0.25, "width": 0.25, "height": 0.5}, "contains_text": True},
        }]
        with self.assertRaises(ContractError):
            validate_schema("reconstruction_plan", plan, SCHEMA_DIR)

    def test_native_text_requires_content_ref(self) -> None:
        plan = valid_plan()
        del plan["elements"][0]["content_ref"]
        with self.assertRaises(ContractError):
            validate_schema("reconstruction_plan", plan, SCHEMA_DIR)


if __name__ == "__main__":
    unittest.main()
