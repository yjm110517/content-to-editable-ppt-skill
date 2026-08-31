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

from handoff_test_support import stage1_authority, stage2_handoff
from schema_utils import ContractError, validate_schema, validate_semantics
from visual_first_handoff import validate_cross_stage


def validate(candidate: dict) -> None:
    validate_schema("stage2_handoff", candidate, SCHEMA_DIR)
    validate_semantics("stage2_handoff", candidate)


class Stage2HandoffTests(unittest.TestCase):
    def test_valid_stage2_contract(self) -> None:
        validate(stage2_handoff("a" * 64))

    def test_unapproved_duplicate_slide_and_duplicate_visual_id_fail(self) -> None:
        unapproved = stage2_handoff("a" * 64)
        unapproved["status"] = "draft"
        duplicate_slide = stage2_handoff("a" * 64)
        duplicate_slide["slides"].append(copy.deepcopy(duplicate_slide["slides"][0]))
        duplicate_object = stage2_handoff("a" * 64)
        duplicate_object["slides"][0]["visual_objects"].append(copy.deepcopy(duplicate_object["slides"][0]["visual_objects"][0]))
        for candidate in (unapproved, duplicate_slide, duplicate_object):
            with self.assertRaises(ContractError):
                validate(candidate)

    def test_visual_object_cannot_carry_content_authority(self) -> None:
        for field in ("text", "content_ref", "data_ref"):
            with self.subTest(field=field):
                candidate = stage2_handoff("a" * 64)
                candidate["slides"][0]["visual_objects"][0][field] = "forbidden"
                with self.assertRaises(ContractError) as raised:
                    validate(candidate)
                self.assertEqual("schema_error", raised.exception.errors[0]["code"])

    def test_visual_spec_path_must_be_json_and_paths_must_be_safe(self) -> None:
        yaml_spec = stage2_handoff("a" * 64)
        yaml_spec["slides"][0]["visual_spec"]["path"] = "visual-specs/S01.yaml"
        escaped = stage2_handoff("a" * 64)
        escaped["slides"][0]["approved_design"]["path"] = "../S01.png"
        for candidate, code in ((yaml_spec, "invalid_visual_spec"), (escaped, "unsafe_path")):
            with self.subTest(code=code):
                with self.assertRaises(ContractError) as raised:
                    validate(candidate)
                self.assertIn(code, {item["code"] for item in raised.exception.errors})

    def test_cross_stage_hash_deck_and_slide_set_gates(self) -> None:
        stage1 = stage1_authority()
        stale = stage2_handoff("b" * 64)
        with self.assertRaises(ContractError) as raised:
            validate_cross_stage(stage1, stale, "a" * 64)
        self.assertEqual("stage1_authority_stale", raised.exception.errors[0]["code"])

        mismatch = stage2_handoff("a" * 64)
        mismatch["slides"][0]["slide_id"] = "S02"
        with self.assertRaises(ContractError) as raised:
            validate_cross_stage(stage1, mismatch, "a" * 64)
        self.assertIn("slide_set_mismatch", {item["code"] for item in raised.exception.errors})

        wrong_deck = stage2_handoff("a" * 64)
        wrong_deck["deck_id"] = "deck_002"
        with self.assertRaises(ContractError) as raised:
            validate_cross_stage(stage1, wrong_deck, "a" * 64)
        self.assertEqual("deck_id_mismatch", raised.exception.errors[0]["code"])

    def test_cross_stage_object_collision_and_overlap_reference_fail(self) -> None:
        stage1 = stage1_authority()
        collision = stage2_handoff("a" * 64)
        collision["slides"][0]["visual_objects"][0]["id"] = "card-01"
        with self.assertRaises(ContractError) as raised:
            validate_cross_stage(stage1, collision, "a" * 64)
        self.assertIn("object_id_collision", {item["code"] for item in raised.exception.errors})

        unknown = stage2_handoff("a" * 64)
        unknown["slides"][0]["visual_objects"][0]["overlaps_with"] = ["missing"]
        with self.assertRaises(ContractError) as raised:
            validate_cross_stage(stage1, unknown, "a" * 64)
        self.assertEqual("unknown_reference", raised.exception.errors[0]["code"])


if __name__ == "__main__":
    unittest.main()
