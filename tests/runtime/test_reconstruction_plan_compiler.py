from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"
sys.path.insert(0, str(SCRIPTS))

from asset_common import AssetError, canonical_json_bytes
from compile_reconstruction_plan import compile_to_iteration
from reconstruction_plan import compile_reconstruction_plan
from schema_utils import ContractError, validate_schema, validate_semantics
from shared_validator import validate_documents


def request() -> dict:
    return {
        "schema_version": "1.3", "task_id": "p1-smoke", "topic": "P1 Compiler", "source_image": "source.png",
        "output_ratio": "16:9", "typography_interaction": "default",
        "typography": {"title_font": "Microsoft YaHei", "title_size_pt": 28, "body_font": "Microsoft YaHei", "body_size_pt": 16},
        "editability_policy": "text-and-structure", "user_requirements": [],
        "review_policy": {"max_iterations": 1, "pass_score": 90, "warning_floor_score": 85, "min_content_accuracy": 98, "required_editability_score": 100, "critical_policy": "by_recoverability"},
    }


def authority() -> dict:
    return {"text_items": [{"id": "title", "text": "Canonical Plan"}]}


def plan() -> dict:
    return {
        "schema_version": "1.0", "page": {"id": "slide_01", "iteration": 1},
        "source": {"approved_design": "source.png"},
        "slide": {"width_in": 13.333, "height_in": 7.5, "background": "#FFFFFF"},
        "elements": [
            {"id": "title", "role": "title", "representation": "native_text", "geometry": {"coordinate_space": "normalized", "x": 0.08, "y": 0.06, "width": 0.4, "height": 0.1}, "z_index": 20, "content_ref": "title", "style": {"font_face": "Microsoft YaHei", "font_size_pt": 28, "bold": True, "color": "#102040"}},
            {"id": "card_1", "role": "card", "representation": "native_shape", "geometry": {"coordinate_space": "normalized", "x": 0.08, "y": 0.3, "width": 0.2, "height": 0.2}, "z_index": 10, "style": {"shape": "roundRect", "fill": {"color": "#FFFFFF"}, "line": {"color": "#336699", "width_pt": 1}}},
            {"id": "card_2", "role": "card", "representation": "native_shape", "geometry": {"coordinate_space": "normalized", "x": 0.36, "y": 0.3, "width": 0.2, "height": 0.2}, "z_index": 10, "style": {"shape": "roundRect", "fill": {"color": "#FFFFFF"}, "line": {"color": "#336699", "width_pt": 1}}},
            {"id": "flow", "role": "connector", "representation": "native_connector", "geometry": {"coordinate_space": "normalized", "x": 0.28, "y": 0.39, "width": 0.08, "height": 0.01}, "z_index": 12, "from_id": "card_1", "to_id": "card_2", "style": {"line": {"color": "#336699", "width_pt": 1.5, "end_arrow": "triangle"}}},
            {"id": "hero", "role": "complex_visual", "representation": "raster_asset", "geometry": {"coordinate_space": "normalized", "x": 0.7, "y": 0.2, "width": 0.2, "height": 0.4}, "z_index": 15, "asset_request": {"source": "approved_design", "source_region": {"coordinate_space": "normalized", "x": 0.5, "y": 0.25, "width": 0.25, "height": 0.5}, "contains_text": False}},
        ],
    }


class ReconstructionPlanCompilerTests(unittest.TestCase):
    def _compile(self, candidate: dict | None = None) -> dict:
        current = candidate or plan()
        validate_schema("reconstruction_plan", current, SCHEMA_DIR)
        validate_semantics("reconstruction_plan", current)
        return compile_reconstruction_plan(current, authority(), request(), {"width_px": 1920, "height_px": 1080})

    def test_compiles_all_p1_representations_and_request_metadata(self) -> None:
        artifacts = self._compile()
        layout = artifacts["layout"]
        self.assertEqual("1.4", layout["schema_version"])
        self.assertEqual({"width_px": 1920, "height_px": 1080}, {key: layout["source"][key] for key in ("width_px", "height_px")})
        self.assertEqual("P1 Compiler", layout["metadata"]["topic"])
        self.assertEqual("default", layout["metadata"]["typography_interaction"])
        self.assertEqual("Canonical Plan", layout["elements"][0]["text"])
        self.assertEqual((0, ""), (layout["elements"][0]["segment_order"], layout["elements"][0]["joiner"]))
        self.assertEqual([960, 270, 1440, 810], artifacts["crops"]["assets"][0]["box_px"])
        self.assertEqual("hero", layout["elements"][-1]["asset_id"])
        self.assertEqual("assets/hero.png", artifacts["asset_manifest"]["assets"][0]["path"])
        paths = {kind: Path(name + ".json") for kind, name in (("layout", "layout"), ("crops", "crops"), ("asset_manifest", "manifest"))}
        validate_documents(artifacts, paths, profile="candidate", schema_dir=SCHEMA_DIR)

    def test_geometry_is_rounded_to_six_decimal_places(self) -> None:
        artifacts = self._compile()
        title = artifacts["layout"]["elements"][0]
        self.assertEqual(1.06664, title["x"])
        self.assertEqual(0.45, title["y"])

    def test_authority_must_be_complete_unique_and_non_overridable(self) -> None:
        candidate = plan()
        candidate["elements"][0]["content_ref"] = "missing"
        with self.assertRaises(ContractError) as raised:
            compile_reconstruction_plan(candidate, authority(), request(), {"width_px": 1920, "height_px": 1080})
        self.assertEqual({"unknown_content_ref", "missing_content_ref"}, {item["code"] for item in raised.exception.errors})

        duplicate = authority()
        duplicate["text_items"].append({"id": "title", "text": "override"})
        with self.assertRaises(ContractError) as raised:
            compile_reconstruction_plan(plan(), duplicate, request(), {"width_px": 1920, "height_px": 1080})
        self.assertEqual("duplicate_content_ref", raised.exception.errors[0]["code"])

    def test_aspect_ratio_gate_rejects_more_than_five_percent(self) -> None:
        candidate = plan()
        candidate["elements"][-1]["geometry"]["width"] = 0.18
        with self.assertRaises(ContractError) as raised:
            self._compile(candidate)
        self.assertEqual("asset_aspect_mismatch", raised.exception.errors[0]["code"])

    def test_aspect_ratio_gate_is_inclusive_at_five_percent(self) -> None:
        candidate = plan()
        raster = candidate["elements"][-1]
        raster["geometry"] = {"coordinate_space": "normalized", "x": 0, "y": 0, "width": 7.5 / 13.333, "height": 1}
        raster["asset_request"]["source_region"] = {"coordinate_space": "normalized", "x": 0, "y": 0, "width": 1, "height": 1}
        for width in (104, 105):
            with self.subTest(width=width):
                compile_reconstruction_plan(candidate, authority(), request(), {"width_px": width, "height_px": 100})
        with self.assertRaises(ContractError) as raised:
            compile_reconstruction_plan(candidate, authority(), request(), {"width_px": 106, "height_px": 100})
        self.assertEqual("asset_aspect_mismatch", raised.exception.errors[0]["code"])

    def test_request_output_ratio_must_match_slide_ratio(self) -> None:
        candidate = plan()
        candidate["slide"].update({"width_in": 10, "height_in": 10})
        with self.assertRaises(ContractError) as raised:
            self._compile(candidate)
        self.assertEqual("slide_ratio_mismatch", raised.exception.errors[0]["code"])

    def test_serialized_outputs_are_byte_deterministic(self) -> None:
        first = self._compile()
        second = self._compile()
        for kind in first:
            self.assertEqual(hashlib.sha256(canonical_json_bytes(first[kind])).hexdigest(), hashlib.sha256(canonical_json_bytes(second[kind])).hexdigest())

    def _work_root(self, root: Path) -> tuple[Path, argparse.Namespace]:
        work = root / "case"
        iteration = work / "iterations" / "01"
        iteration.mkdir(parents=True)
        Image.new("RGB", (1920, 1080), "#7CB9E8").save(work / "source.png")
        (work / "request.json").write_text(json.dumps(request(), ensure_ascii=False), encoding="utf-8")
        (work / "source-content.json").write_text(json.dumps(authority(), ensure_ascii=False), encoding="utf-8")
        plan_path = iteration / "reconstruction-plan.json"
        plan_path.write_text(json.dumps(plan(), ensure_ascii=False), encoding="utf-8")
        return work, argparse.Namespace(plan=plan_path, content=work / "source-content.json", iteration_dir=iteration, schema_dir=SCHEMA_DIR, force=False)

    def test_cli_adapter_reads_image_dimensions_and_enforces_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, args = self._work_root(Path(temporary))
            outputs = compile_to_iteration(args)
            layout = json.loads(Path(outputs["layout"]).read_text(encoding="utf-8"))
            self.assertEqual((1920, 1080), (layout["source"]["width_px"], layout["source"]["height_px"]))
            with self.assertRaises(AssetError) as raised:
                compile_to_iteration(args)
            self.assertEqual("output_collision", raised.exception.detail["code"])
            args.force = True
            compile_to_iteration(args)

    def test_validation_failure_writes_no_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, args = self._work_root(Path(temporary))
            candidate = plan()
            candidate["elements"][-1]["geometry"]["width"] = 0.18
            args.plan.write_text(json.dumps(candidate), encoding="utf-8")
            with self.assertRaises(AssetError) as raised:
                compile_to_iteration(args)
            self.assertEqual("asset_aspect_mismatch", raised.exception.detail["code"])
            for name in ("layout.json", "crops.json", "asset_manifest.json"):
                self.assertFalse((args.iteration_dir / name).exists())

    def test_cli_preserves_reconstruction_plan_error_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work, args = self._work_root(Path(temporary))
            candidate = plan()
            candidate["elements"][0] = {
                "id": "chart", "role": "chart", "representation": "native_chart",
                "geometry": {"coordinate_space": "normalized", "x": 0.1, "y": 0.1, "width": 0.4, "height": 0.3}, "z_index": 1,
            }
            args.plan.write_text(json.dumps(candidate), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable, str(SCRIPTS / "compile_reconstruction_plan.py"), "--plan", str(args.plan),
                    "--content", str(work / "source-content.json"), "--iteration-dir", str(args.iteration_dir),
                    "--schema-dir", str(SCHEMA_DIR),
                ],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(4, completed.returncode)
            self.assertEqual("unsupported_representation", payload["error"]["category"])

    @unittest.skipUnless(os.environ.get("IVT_RUN_POWERPOINT_SMOKE") == "1", "set IVT_RUN_POWERPOINT_SMOKE=1 to run PowerPoint smoke")
    def test_powerpoint_single_page_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work, args = self._work_root(Path(temporary))
            compile_to_iteration(args)
            iteration = args.iteration_dir
            command = [
                sys.executable, str(SCRIPTS / "run_pipeline.py"), "--request", str(work / "request.json"),
                "--iteration-dir", str(iteration), "--output-ppt", str(iteration / "p1-smoke.pptx"),
                "--execution-mode", "diagnostic", "--renderer", "powerpoint", "--schema-dir", str(SCHEMA_DIR),
                "--run-id", "p1-smoke", "--iteration", "1",
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            qa_path = iteration / "qa_report.json"
            evidence = qa_path.read_text(encoding="utf-8") if qa_path.is_file() else ""
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr + evidence)
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            self.assertEqual("pass", qa["status"])
            manifest = json.loads((iteration / "asset_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("passed", manifest["assets"][0]["security_status"])


if __name__ == "__main__":
    unittest.main()
