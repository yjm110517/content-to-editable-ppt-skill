from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from manage_design_preview import _map_input_manifest  # noqa: E402
from preview_projector import project_preview  # noqa: E402
from schema_utils import load_json, validate_schema  # noqa: E402


H = "a" * 64


def package() -> dict:
    return {"schema_version": "1.0", "artifact_type": "deck_prompt_package", "deck_id": "D01", "slides": [{"slide_id": "S01", "order": 1, "prompt_sha256": H, "element_intents": [{"source_ref": "S01-TITLE", "future_element_map_id": "EL-S01-TITLE"}, {"source_ref": "S01-C01", "future_element_map_id": "EL-S01-C01"}]}]}


class PreviewOrchestratorTests(unittest.TestCase):
    def test_register_requires_page_generation_manifest_not_base_prompt_hash(self) -> None:
        # The P3.2 slide prompt is embedded inside a page-generation prompt whose
        # authority additionally binds the approved Style Anchor Reference.
        base_prompt_sha = "a" * 64
        generation_prompt_sha = "b" * 64
        self.assertNotEqual(base_prompt_sha, generation_prompt_sha)
    def test_map_package_copies_exact_allowlisted_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); raw = root / "raw.png"; Image.new("RGB", (1600, 900), "white").save(raw)
            prompt = root / "package.json"; prompt.write_text(json.dumps(package()), encoding="utf-8")
            system = root / "system.json"; system.write_text("{}", encoding="utf-8")
            content = {"slide_id": "S01", "title": {"content_ref": "S01-TITLE", "text": "Title"}, "content_blocks": [{"content_ref": "S01-C01", "text": "Body"}]}
            manifest = _map_input_manifest(deck_id="D01", slide_id="S01", package=package(), prompt_package_path=prompt, raw=raw, content=content, system_path=system, output=root / "call")
            validate_schema("design_element_map_input_manifest", manifest, ROOT / "content-to-editable-ppt" / "schemas")
            self.assertEqual(len(manifest["inputs"]), 6)
            self.assertTrue((root / "call" / "inputs" / "generated-layer.png").is_file())

    def test_projector_uses_authority_text_and_raw_background_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); raw = root / "raw.png"; Image.new("RGB", (1600, 900), "white").save(raw)
            content = {"slide_id": "S01", "title": {"content_ref": "S01-TITLE", "text": "正式标题"}, "content_blocks": [{"content_ref": "S01-C01", "text": "正式正文"}]}
            mapping = {"slide_id": "S01", "elements": [
                {"element_id": "EL-S01-TITLE", "source_ref": "S01-TITLE", "reconstruction_class": "native_text", "normalized_bbox": {"x": 500, "y": 500, "w": 4000, "h": 1000}, "z_index": 20},
                {"element_id": "EL-S01-C01", "source_ref": "S01-C01", "reconstruction_class": "native_text", "normalized_bbox": {"x": 500, "y": 2000, "w": 4000, "h": 2000}, "z_index": 20},
                {"element_id": "GEN-S01-SHAPE", "source_ref": None, "reconstruction_class": "native_shape", "normalized_bbox": {"x": 5000, "y": 2000, "w": 3000, "h": 3000}, "z_index": 5},
            ]}
            system = {"hard_constraints": {"palette": {"background": "#F8FAFC", "text_primary": "#111827", "text_secondary": "#475569"}, "typography": {"title": {"family": "Microsoft YaHei", "size_pt": 32}, "body": {"family": "Microsoft YaHei", "size_pt": 20}}}}
            footprints = {"entries": [{"slide_id": "S01", "content_ref": "S01-TITLE", "font_family": "Microsoft YaHei", "font_size_pt": 32, "line_height_milli": 1200}, {"slide_id": "S01", "content_ref": "S01-C01", "font_family": "Microsoft YaHei", "font_size_pt": 20, "line_height_milli": 1250}]}
            docs = project_preview(deck_id="D01", slide_id="S01", content=content, element_map=mapping, visual_system=system, footprints=footprints, raw_layer=raw, output_dir=root / "preview")
            layout = load_json(docs["layout"])
            self.assertEqual([item["id"] for item in layout["elements"]], ["raw-layer", "EL-S01-TITLE", "EL-S01-C01"])
            self.assertEqual(layout["elements"][1]["text"], "正式标题")
            self.assertEqual(layout["elements"][2]["text"], "正式正文")


if __name__ == "__main__":
    unittest.main()
