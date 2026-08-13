from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
VENDOR = ROOT / "content-to-editable-ppt" / "runtime" / "vendor" / "tabler-icons" / "3.46.0"
sys.path.insert(0, str(SCRIPTS))

from generate_icon_fallback import compose, draw, handoff
from build_tabler_icon_index import build_index
from resolve_icon_asset import materialize, verify
from schema_utils import ContractError
from tests.runtime.test_p3_icon_resolution_materialization import IconResolutionMaterializationTests


NOW = "2026-08-13T00:00:00Z"


class IconFallbackTests(unittest.TestCase):
    def authority(self, root: Path) -> dict[str, Path]:
        root.mkdir(parents=True, exist_ok=True)
        helper = IconResolutionMaterializationTests()
        helper.index = build_index(VENDOR)
        return helper.fixture(root)

    def common(self, paths: dict[str, Path]) -> dict:
        return {
            "p2_manifest": paths["p2_manifest"], "wireframe_root": paths["wireframe_root"],
            "visual_direction": paths["direction"], "visual_ref": "S01-V01", "created_at_utc": NOW,
        }

    def test_two_icon_composition_is_deterministic_and_uses_unified_materializer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_paths = self.authority(root / "first")
            second_paths = self.authority(root / "second")
            outputs = []
            for index, paths in enumerate((first_paths, second_paths), 1):
                source = root / f"composition-{index}.svg"
                record = root / f"composition-{index}.json"
                compose(argparse.Namespace(**self.common(paths), vendor_root=VENDOR, icon_name=["code", "sparkles"], output_source=source, output_record=record))
                materialize(argparse.Namespace(resolution_record=record, vendor_root=None, source_svg=source, output_dir=root / f"resolved-{index}" / "assets"))
                verify(argparse.Namespace(
                    **self.common(paths), search_evidence=None, resolution_record=record, vendor_root=None, source_svg=source,
                    asset_manifest=root / f"resolved-{index}" / "asset_manifest.json",
                    security_report=root / f"resolved-{index}" / "svg_security_report.json",
                    consumption_contract=root / f"resolved-{index}" / "consumption-contract.json",
                ))
                outputs.append((source, root / f"resolved-{index}" / "assets" / "S01-V01.sanitized.svg"))
                self.assertEqual(json.loads((root / f"resolved-{index}" / "asset_manifest.json").read_text())["assets"][0]["source"], "composite")
            self.assertEqual(outputs[0][0].read_bytes(), outputs[1][0].read_bytes())
            self.assertEqual(outputs[0][1].read_bytes(), outputs[1][1].read_bytes())

    def test_third_composition_icon_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.authority(root)
            with self.assertRaises(ContractError) as raised:
                compose(argparse.Namespace(**self.common(paths), vendor_root=VENDOR, icon_name=["code", "sparkles", "robot"], output_source=root / "x.svg", output_record=root / "x.json"))
            self.assertIn("composition_limit", {item["code"] for item in raised.exception.errors})

    def test_programmatic_primitives_are_bounded_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.authority(root)
            drawing = {
                "schema_version": "1.0", "artifact_type": "simple_icon_drawing", "visual_ref": "S01-V01",
                "width": 24, "height": 24,
                "primitives": [
                    {"type": "rect", "x": 3, "y": 4, "width": 18, "height": 14, "rx": 2},
                    {"type": "arrow", "x1": 7, "y1": 12, "x2": 17, "y2": 12},
                ],
            }
            drawing_path = root / "drawing.json"
            drawing_path.write_text(json.dumps(drawing), encoding="utf-8")
            sources = []
            for index in (1, 2):
                source, record = root / f"draw-{index}.svg", root / f"draw-{index}.json"
                draw(argparse.Namespace(**self.common(paths), drawing=drawing_path, output_source=source, output_record=record))
                sources.append(source.read_bytes())
            self.assertEqual(sources[0], sources[1])
            materialize(argparse.Namespace(resolution_record=root / "draw-1.json", vendor_root=None, source_svg=root / "draw-1.svg", output_dir=root / "draw-resolved" / "assets"))
            self.assertEqual(json.loads((root / "draw-resolved" / "asset_manifest.json").read_text())["assets"][0]["source"], "programmatic")

    def test_raw_path_text_external_and_over_limits_are_schema_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.authority(root)
            cases = [
                {"type": "path", "d": "M0 0"},
                {"type": "text", "text": "AI"},
                {"type": "image", "href": "https://example.com/x.png"},
            ]
            for index, primitive in enumerate(cases):
                drawing = {"schema_version": "1.0", "artifact_type": "simple_icon_drawing", "visual_ref": "S01-V01", "width": 24, "height": 24, "primitives": [primitive]}
                path = root / f"bad-{index}.json"; path.write_text(json.dumps(drawing), encoding="utf-8")
                with self.assertRaises(ContractError):
                    draw(argparse.Namespace(**self.common(paths), drawing=path, output_source=root / f"bad-{index}.svg", output_record=root / f"bad-{index}-record.json"))
            too_many = {"schema_version": "1.0", "artifact_type": "simple_icon_drawing", "visual_ref": "S01-V01", "width": 24, "height": 24, "primitives": [{"type": "line", "x1": 0, "y1": 0, "x2": 1, "y2": 1}] * 13}
            path = root / "many.json"; path.write_text(json.dumps(too_many), encoding="utf-8")
            with self.assertRaises(ContractError):
                draw(argparse.Namespace(**self.common(paths), drawing=path, output_source=root / "many.svg", output_record=root / "many-record.json"))

    def test_group_depth_and_out_of_bounds_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.authority(root)
            nested = {"type": "line", "x1": 0, "y1": 0, "x2": 1, "y2": 1}
            for _ in range(4):
                nested = {"type": "group", "children": [nested]}
            for name, primitive in (("deep", nested), ("bounds", {"type": "rect", "x": 20, "y": 20, "width": 8, "height": 8})):
                drawing = {"schema_version": "1.0", "artifact_type": "simple_icon_drawing", "visual_ref": "S01-V01", "width": 24, "height": 24, "primitives": [primitive]}
                path = root / f"{name}.json"; path.write_text(json.dumps(drawing), encoding="utf-8")
                with self.assertRaises(ContractError):
                    draw(argparse.Namespace(**self.common(paths), drawing=path, output_source=root / f"{name}.svg", output_record=root / f"{name}-record.json"))

    def test_raster_handoff_is_terminal_and_does_not_create_svg_success_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.authority(root)
            output = root / "raster-handoff.json"
            result = handoff(argparse.Namespace(**self.common(paths), reason="no_suitable_svg", output=output))
            self.assertEqual(result["status"], "raster_handoff_required")
            self.assertFalse((root / "asset_manifest.json").exists())
            self.assertFalse((root / "consumption-contract.json").exists())
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertNotIn("sanitized_svg_sha256", record)


if __name__ == "__main__":
    unittest.main()
