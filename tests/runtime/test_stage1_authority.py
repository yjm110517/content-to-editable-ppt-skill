from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from handoff_test_support import stage1_authority
from schema_utils import ContractError, validate_schema, validate_semantics


def validate(candidate: dict) -> None:
    validate_schema("stage1_authority", candidate, SCHEMA_DIR)
    validate_semantics("stage1_authority", candidate)


class Stage1AuthorityTests(unittest.TestCase):
    def test_valid_authority_with_numeric_chart_and_table_data(self) -> None:
        validate(stage1_authority())

    def test_slide_ids_and_orders_are_unique_and_contiguous(self) -> None:
        for mutation in ("duplicate_id", "duplicate_order", "gap"):
            with self.subTest(mutation=mutation):
                candidate = stage1_authority()
                second = copy.deepcopy(candidate["slides"][0])
                second["slide_id"] = "S02"
                second["order"] = 2
                candidate["slides"].append(second)
                if mutation == "duplicate_id":
                    candidate["slides"][1]["slide_id"] = "S01"
                elif mutation == "duplicate_order":
                    candidate["slides"][1]["order"] = 1
                else:
                    candidate["slides"][1]["order"] = 3
                with self.assertRaises(ContractError):
                    validate(candidate)

    def test_duplicate_local_ids_are_rejected(self) -> None:
        mutations = (
            ("text_items", "S01-title"),
            ("objects", "title-object"),
            ("structured_data", "data-chart-01"),
        )
        for field, duplicate_id in mutations:
            with self.subTest(field=field):
                candidate = stage1_authority()
                item = copy.deepcopy(candidate["slides"][0][field][0])
                item["id"] = duplicate_id
                candidate["slides"][0][field].append(item)
                with self.assertRaises(ContractError):
                    validate(candidate)

    def test_object_authority_references_must_resolve(self) -> None:
        cases = ((0, "content_ref", "unknown_content_ref"), (4, "data_ref", "unknown_data_ref"), (3, "relation_ref", "unknown_relation_ref"))
        for index, field, code in cases:
            with self.subTest(field=field):
                candidate = stage1_authority()
                candidate["slides"][0]["objects"][index][field] = "missing"
                with self.assertRaises(ContractError) as raised:
                    validate(candidate)
                self.assertIn(code, {item["code"] for item in raised.exception.errors})

    def test_connector_cannot_duplicate_relation_endpoints(self) -> None:
        candidate = stage1_authority()
        candidate["slides"][0]["objects"][3]["from_id"] = "card-01"
        with self.assertRaises(ContractError) as raised:
            validate(candidate)
        self.assertEqual("schema_error", raised.exception.errors[0]["code"])

    def test_semantic_structure_references_and_self_reference_are_rejected(self) -> None:
        candidates = []
        region = stage1_authority()
        region["slides"][0]["semantic_structure"]["regions"][0]["members"][0] = "missing"
        candidates.append((region, "unknown_reference"))
        reading = stage1_authority()
        reading["slides"][0]["semantic_structure"]["reading_order"][0] = "missing"
        candidates.append((reading, "unknown_reference"))
        relation = stage1_authority()
        relation["slides"][0]["semantic_structure"]["relations"][0]["to_id"] = "card-01"
        candidates.append((relation, "self_reference"))
        duplicate_reading = stage1_authority()
        duplicate_reading["slides"][0]["semantic_structure"]["reading_order"].append("card-01")
        candidates.append((duplicate_reading, "schema_error"))
        for candidate, code in candidates:
            with self.subTest(code=code):
                with self.assertRaises(ContractError) as raised:
                    validate(candidate)
                self.assertIn(code, {item["code"] for item in raised.exception.errors})

    def test_structured_data_dimensions_must_be_consistent(self) -> None:
        chart = stage1_authority()
        chart["slides"][0]["structured_data"][0]["series"][0]["values"] = [1]
        table = stage1_authority()
        table["slides"][0]["structured_data"][1]["rows"][0] = ["Experimental"]
        for candidate in (chart, table):
            with self.assertRaises(ContractError) as raised:
                validate(candidate)
            self.assertEqual("structured_data_shape", raised.exception.errors[0]["code"])


if __name__ == "__main__":
    unittest.main()
