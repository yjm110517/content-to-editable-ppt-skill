from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from deck_build_request import load_request, stage_assets, validate_request
from schema_utils import ContractError


def request() -> dict:
    return {
        "schema_version": "1.0",
        "artifact_type": "deck_build_request",
        "task_id": "direct-deck-test",
        "deck_id": "DIRECT-001",
        "output_name": "direct_deck",
        "topic": "Direct deck",
        "objective": "Verify direct editable deck construction",
        "audience": "Test users",
        "language": "en-US",
        "output_ratio": "16:9",
        "confirmation_status": "confirmed",
        "styles": {"body": {"font_face": "Arial", "font_size_pt": 18, "color": "#111111"}},
        "slides": [
            {
                "slide_id": "S01",
                "order": 1,
                "background": "#FFFFFF",
                "elements": [
                    {"id": "TITLE", "type": "text", "x": 0.6, "y": 0.4, "w": 5.0, "h": 0.7, "z_index": 10, "editable": True, "text": "Direct deck", "content_ref": "S01-TITLE", "style_ref": "body"},
                    {"id": "CARD", "type": "shape", "x": 0.6, "y": 1.5, "w": 4.0, "h": 2.0, "z_index": 1, "editable": True, "shape": "roundRect", "fill": {"color": "#F2F5FA"}},
                ],
            }
        ],
        "assets": [],
    }


class DirectDeckRequestTests(unittest.TestCase):
    def test_minimal_request_is_valid(self):
        self.assertEqual(validate_request(request())["deck_id"], "DIRECT-001")

    def test_order_duplicate_ids_and_unknown_style_are_rejected(self):
        value = request()
        second = copy.deepcopy(value["slides"][0]); second["slide_id"] = "S02"; second["order"] = 3
        value["slides"].append(second)
        value["slides"][0]["elements"].append(copy.deepcopy(value["slides"][0]["elements"][0]))
        value["slides"][0]["elements"][0]["style_ref"] = "missing"
        with self.assertRaises(ContractError) as caught:
            validate_request(value)
        codes = {item["code"] for item in caught.exception.errors}
        self.assertTrue({"invalid_slide_order", "duplicate_element_id", "unknown_style"}.issubset(codes))

    def test_geometry_and_image_text_overlap_are_rejected(self):
        value = request()
        value["assets"] = [{"asset_id": "IMAGE", "path": "image.png", "sha256": "a" * 64, "media_type": "image/png", "contains_text": False, "text_editability_exempt": False}]
        value["slides"][0]["elements"].append({"id": "IMAGE", "type": "image", "x": 0.5, "y": 0.3, "w": 2.0, "h": 1.0, "z_index": 0, "editable": False, "asset_id": "IMAGE", "fit": "contain", "preserve_aspect_ratio": True})
        with self.assertRaises(ContractError) as caught:
            validate_request(value)
        self.assertIn("image_text_overlap", {item["code"] for item in caught.exception.errors})

    def test_cross_slide_element_ids_may_repeat(self):
        value = request()
        second = copy.deepcopy(value["slides"][0]); second["slide_id"] = "S02"; second["order"] = 2
        value["slides"].append(second)
        validate_request(value)

    def test_png_asset_is_decoded_hashed_and_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source_root = root / "input"; source_root.mkdir(); source = source_root / "image.png"
            Image.new("RGB", (20, 10), "blue").save(source)
            value = request(); value["assets"] = [{"asset_id": "IMAGE", "path": "image.png", "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "media_type": "image/png", "contains_text": False, "text_editability_exempt": False}]
            staged = stage_assets(validate_request(value), source_root, root / "staged")
            self.assertEqual(staged[0]["width_px"], 20); self.assertTrue(Path(staged[0]["path"]).is_file())

    def test_asset_path_escape_and_hash_mismatch_fail(self):
        value = request(); value["assets"] = [{"asset_id": "IMAGE", "path": "../image.png", "sha256": "a" * 64, "media_type": "image/png", "contains_text": False, "text_editability_exempt": False}]
        with self.assertRaises(ContractError): validate_request(value)

    def test_load_request_requires_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception): load_request(Path(tmp) / "missing.json")

    def test_output_name_cannot_be_an_extension_bearing_component(self):
        value = request(); value["output_name"] = "direct_deck.pptx"
        with self.assertRaises(ContractError):
            validate_request(value)


if __name__ == "__main__":
    unittest.main()
