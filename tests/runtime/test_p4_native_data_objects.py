from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
SCHEMAS = ROOT / "content-to-editable-ppt" / "schemas"
sys.path.insert(0, str(SCRIPTS))

from pptx_native_signature import NS, chart_layout_signature, chart_signature, native_data_signatures, native_type, object_name, table_layout_signature, table_signature
from reconstruction_plan import compile_reconstruction_plan
from asset_common import atomic_write_json
from finalize_agent_response import _finalize_initial
from schema_utils import ContractError, validate_schema, validate_semantics
from visual_first_planner import validate_block_against_handoff, validate_plan_against_handoff
from tests.runtime.handoff_test_support import request as runtime_request


def geometry(x: float, y: float, width: float, height: float) -> dict:
    return {"coordinate_space": "normalized", "x": x, "y": y, "width": width, "height": height}


def request() -> dict:
    return {
        "topic": "实验结果概览",
        "source_image": "source.png",
        "output_ratio": "16:9",
        "typography_interaction": "default",
    }


def structured_data() -> list[dict]:
    return [
        {
            "id": "data-chart-01",
            "kind": "chart",
            "categories": ["实验组", "对照组"],
            "series": [{"name": "后测", "values": [79.50, 73.78]}],
            "chart_type": "vertical_bar",
            "category_axis_label": "组别",
            "value_axis_label": "得分",
            "unit": "分",
        },
        {
            "id": "data-table-01",
            "kind": "table",
            "grid": [
                ["实验结果", None, None],
                ["组别", "Mean", "SD"],
                ["实验组", 79.50, 12.52],
                ["对照组", 73.78, 17.93],
            ],
            "header_row_count": 2,
            "merges": [{"row": 0, "column": 0, "row_span": 1, "column_span": 3}],
        },
    ]


def plan() -> dict:
    return {
        "schema_version": "1.1",
        "page": {"id": "S01", "iteration": 1},
        "source": {"approved_design": "source.png"},
        "slide": {"width_in": 13.333, "height_in": 7.5, "background": "#FFFFFF"},
        "elements": [
            {
                "id": "title-object", "role": "title", "representation": "native_text",
                "geometry": geometry(0.05, 0.04, 0.9, 0.1), "z_index": 1,
                "content_ref": "title-content",
                "style": {"font_face": "Microsoft YaHei", "font_size_pt": 28, "color": "#102040"},
            },
            {
                "id": "chart-01", "role": "chart", "representation": "native_chart",
                "geometry": geometry(0.05, 0.2, 0.42, 0.65), "z_index": 2,
                "data_ref": "data-chart-01",
                "style": {"chart_type": "vertical_bar", "show_legend": False, "show_value": True, "number_format": "0.00", "color_tokens": ["#4472C4"], "font_face": "Microsoft YaHei"},
            },
            {
                "id": "table-01", "role": "table", "representation": "native_table",
                "geometry": geometry(0.53, 0.25, 0.4, 0.48), "z_index": 2,
                "data_ref": "data-table-01",
                "style": {
                    "font_face": "Microsoft YaHei", "font_size_pt": 13, "color": "#102040",
                    "header_fill": "#D9E7F7", "header_bold": True, "body_fill": "#FFFFFF",
                    "border_color": "#5B9BD5", "border_width_pt": 1, "align": "center", "valign": "middle",
                    "margin_in": 0.04, "number_format": "0.00",
                    "column_width_ratios": [2, 1, 1], "row_height_ratios": [1, 1, 1, 1],
                },
            },
        ],
    }


def handoff() -> dict:
    return {
        "schema_version": "1.1", "deck_id": "deck-01", "slide_id": "S01", "order": 1,
        "provenance": {name: "0" * 64 for name in ("stage1_authority_sha256", "stage2_handoff_sha256", "approved_design_sha256", "wireframe_sha256", "visual_spec_sha256")},
        "page": {"section": "", "role": "overview", "key_message": "实验结果概览", "source_refs": [], "visual_need": "chart and table", "wireframe": "wireframe.md"},
        "content": {"text_items": [{"id": "title-content", "role": "title", "text": "实验结果概览"}]},
        "semantic_structure": {
            "objects": [
                {"id": "title-object", "kind": "text", "role": "title", "content_ref": "title-content"},
                {"id": "chart-01", "kind": "chart", "role": "evidence", "data_ref": "data-chart-01"},
                {"id": "table-01", "kind": "table", "role": "detail", "data_ref": "data-table-01"},
            ],
            "regions": [{"id": "main", "role": "main", "members": ["chart-01", "table-01"]}],
            "reading_order": ["title-object", "chart-01", "table-01"], "relations": [],
        },
        "structured_data": structured_data(),
        "stage2": {"approved_design": "source.png", "visual_spec": "visual-spec.json", "visual_objects": []},
    }


def stage1_authority() -> dict:
    structure = copy.deepcopy(handoff()["semantic_structure"])
    structure.pop("objects")
    return {
        "schema_version": "1.1", "status": "approved", "deck_id": "deck-01",
        "brief": {"topic": "实验结果概览", "audience": "教师", "objective": "展示结果", "presentation_type": "report", "language": "zh-CN"},
        "slides": [{
            "slide_id": "S01", "order": 1, "section": "", "role": "overview", "key_message": "实验结果概览", "source_refs": [], "visual_need": "chart and table",
            "wireframe": {"path": "wireframes/S01.md", "sha256": "0" * 64},
            "text_items": [{"id": "title-content", "role": "title", "text": "实验结果概览"}],
            "objects": handoff()["semantic_structure"]["objects"],
            "semantic_structure": structure, "structured_data": structured_data(),
        }],
    }


class P4NativeDataObjectsTests(unittest.TestCase):
    def test_stage1_v11_validates_grid_merges_and_legacy_row_length(self) -> None:
        authority = stage1_authority()
        validate_schema("stage1_authority", authority, SCHEMAS)
        validate_semantics("stage1_authority", authority)

        legacy = copy.deepcopy(authority)
        legacy["schema_version"] = "1.0"
        legacy_table = legacy["slides"][0]["structured_data"][1]
        legacy_table.clear()
        legacy_table.update({"id": "data-table-01", "kind": "table", "columns": ["A", "B"], "rows": [["only-one"]]})
        validate_schema("stage1_authority", legacy, SCHEMAS)
        with self.assertRaises(ContractError) as raised:
            validate_semantics("stage1_authority", legacy)
        self.assertIn("structured_data_shape", {item["code"] for item in raised.exception.errors})

        invalid_merge = copy.deepcopy(authority)
        invalid_merge["slides"][0]["structured_data"][1]["merges"].append({"row": 0, "column": 1, "row_span": 1, "column_span": 2})
        with self.assertRaises(ContractError) as raised:
            validate_semantics("stage1_authority", invalid_merge)
        self.assertIn("structured_data_shape", {item["code"] for item in raised.exception.errors})

    def test_compiler_projects_chart_and_table_without_copying_plan_data(self) -> None:
        current = plan()
        validate_schema("reconstruction_plan", current, SCHEMAS)
        validate_semantics("reconstruction_plan", current)
        artifacts = compile_reconstruction_plan(
            current, {"text_items": [{"id": "title-content", "text": "实验结果概览"}]}, request(),
            {"width_px": 1600, "height_px": 900}, structured_data(),
        )
        layout = artifacts["layout"]
        self.assertEqual("1.5", layout["schema_version"])
        chart = next(item for item in layout["elements"] if item["id"] == "chart-01")
        self.assertEqual("chart", chart["type"])
        self.assertEqual("data-chart-01", chart["data_ref"])
        self.assertEqual(100, chart["value_scale"])
        self.assertEqual([7950, 7378], chart["series"][0]["values"])
        table = next(item for item in layout["elements"] if item["id"] == "table-01")
        self.assertEqual("table", table["type"])
        self.assertEqual(["实验结果", "", ""], table["grid"][0])
        self.assertEqual("79.50", table["grid"][2][1])
        self.assertEqual([{"row": 0, "column": 0, "row_span": 1, "column_span": 3}], table["merges"])
        validate_schema("layout", layout, SCHEMAS)
        validate_semantics("layout", layout)

    def test_compiler_requires_matching_structured_data(self) -> None:
        current = plan()
        with self.assertRaises(ContractError) as raised:
            compile_reconstruction_plan(
                current, {"text_items": [{"id": "title-content", "text": "实验结果概览"}]}, request(),
                {"width_px": 1600, "height_px": 900}, None,
            )
        self.assertIn("missing_structured_data", {item["code"] for item in raised.exception.errors})

        mismatched = copy.deepcopy(structured_data())
        mismatched[0]["kind"] = "table"
        with self.assertRaises(ContractError) as raised:
            compile_reconstruction_plan(
                current, {"text_items": [{"id": "title-content", "text": "实验结果概览"}]}, request(),
                {"width_px": 1600, "height_px": 900}, mismatched,
            )
        self.assertIn("data_type_mismatch", {item["code"] for item in raised.exception.errors})

    def test_planner_enforces_native_data_identity_and_chart_type(self) -> None:
        validate_plan_against_handoff(plan(), handoff(), request(), iteration=1, slide_id="S01")
        fallback = copy.deepcopy(plan())
        next(item for item in fallback["elements"] if item["id"] == "chart-01")["representation"] = "raster_asset"
        with self.assertRaises(ContractError) as raised:
            validate_plan_against_handoff(fallback, handoff(), request(), iteration=1, slide_id="S01")
        self.assertIn("representation_mismatch", {item["code"] for item in raised.exception.errors})

        type_change = copy.deepcopy(plan())
        next(item for item in type_change["elements"] if item["id"] == "chart-01")["style"]["chart_type"] = "line"
        with self.assertRaises(ContractError) as raised:
            validate_plan_against_handoff(type_change, handoff(), request(), iteration=1, slide_id="S01")
        self.assertIn("data_identity_mismatch", {item["code"] for item in raised.exception.errors})

    def test_unsupported_stage1_chart_type_is_preserved_for_object_block(self) -> None:
        authority = stage1_authority()
        authority["slides"][0]["structured_data"][0]["chart_type"] = "scatter"
        validate_schema("stage1_authority", authority, SCHEMAS)
        validate_semantics("stage1_authority", authority)
        current_handoff = handoff()
        current_handoff["structured_data"][0]["chart_type"] = "scatter"
        validate_block_against_handoff(
            {"code": "unsupported_reconstruction", "scope": "objects", "object_ids": ["chart-01"]},
            current_handoff,
        )
        with self.assertRaises(ContractError) as raised:
            validate_plan_against_handoff(plan(), current_handoff, request(), iteration=1, slide_id="S01")
        self.assertIn("unsupported_reconstruction", {item["code"] for item in raised.exception.errors})

    def test_p3_finalizer_passes_handoff_structured_data_to_p1_core(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary) / "work"
            (work / "iterations").mkdir(parents=True)
            current_handoff = handoff()
            atomic_write_json(work / "request.json", request())
            atomic_write_json(work / "source-content.json", {"text_items": [{"id": "title-content", "text": "实验结果概览"}]})
            atomic_write_json(work / "reconstruction-handoff.json", current_handoff)
            (work / "visual-spec.json").write_text("{}", encoding="utf-8")
            Image.new("RGB", (1600, 900), "#DDEEFF").save(work / "source.png")
            call_dir = work / ".agent-calls" / "01" / "planner" / "p4-fixture"
            (call_dir / "inputs").mkdir(parents=True)
            atomic_write_json(call_dir / "inputs" / "request.json", request())
            atomic_write_json(call_dir / "inputs" / "reconstruction-handoff.json", current_handoff)
            args = type("Args", (), {"output_dir": work / "iterations" / "01", "call_dir": call_dir, "schema_dir": SCHEMAS, "iteration": 1})()
            result = _finalize_initial(args, {"slide_id": "S01"}, {"outcome": "plan", "artifacts": {"reconstruction_plan": plan()}})
            self.assertEqual("planned", result["planner_status"])
            layout = json.loads((args.output_dir / "layout.json").read_text(encoding="utf-8"))
            self.assertEqual("1.5", layout["schema_version"])
            self.assertEqual({"chart", "table"}, {item["type"] for item in layout["elements"] if item["type"] in {"chart", "table"}})

    def test_shared_builder_emits_native_chart_and_table(self) -> None:
        artifacts = compile_reconstruction_plan(
            plan(), {"text_items": [{"id": "title-content", "text": "实验结果概览"}]}, request(),
            {"width_px": 1600, "height_px": 900}, structured_data(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            iteration = Path(temporary) / "iterations" / "01"
            iteration.mkdir(parents=True)
            for name, document in artifacts.items():
                (iteration / f"{name}.json").write_text(json.dumps(document), encoding="utf-8")
            (iteration / "assets").mkdir()
            output = iteration / "native-data.pptx"
            summary = iteration / "build_summary.json"
            completed = subprocess.run(
                [
                    "node", str(SCRIPTS / "build_slide.mjs"), "--iteration-dir", str(iteration),
                    "--layout", str(iteration / "layout.json"), "--asset-manifest", str(iteration / "asset_manifest.json"),
                    "--asset-dir", str(iteration / "assets"), "--output", str(output), "--build-summary", str(summary),
                    "--python", sys.executable, "--run-id", "p4-native-data", "--iteration", "1", "--schema-dir", str(SCHEMAS),
                ], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            built = json.loads(summary.read_text(encoding="utf-8"))
            self.assertEqual("1.4", built["schema_version"])
            self.assertEqual({"data-chart-01", "data-table-01"}, {item["data_ref"] for item in built["element_map"] if "data_ref" in item})
            with zipfile.ZipFile(output) as archive:
                slide = ET.fromstring(archive.read("ppt/slides/slide1.xml"))
                shapes = {
                    object_name(shape): shape
                    for shape in slide.findall(".//p:spTree/*", NS)
                    if object_name(shape)
                }
                chart_shape = shapes["ivt:chart-01"]
                table_shape = shapes["ivt:table-01"]
                self.assertEqual("chart", native_type(chart_shape))
                self.assertEqual("table", native_type(table_shape))
                self.assertEqual(chart_layout_signature(artifacts["layout"]["elements"][1]), chart_signature(archive, 1, chart_shape))
                chart_xml = ET.fromstring(archive.read(next(name for name in archive.namelist() if name.startswith("ppt/charts/chart") and name.endswith(".xml"))))
                chart_label_format = chart_xml.find(".//c:dLbls/c:numFmt", NS)
                self.assertIsNotNone(chart_label_format)
                self.assertEqual("0.00", chart_label_format.attrib.get("formatCode"))
                table_actual = table_signature(table_shape)
                table_expected = table_layout_signature(artifacts["layout"]["elements"][2])
                self.assertIsNotNone(table_actual)
                self.assertEqual(table_expected["column_count"], table_actual["column_count"])
                self.assertEqual(
                    [[cell["text"] for cell in row] for row in table_expected["rows"]],
                    [[cell["text"] for cell in row] for row in table_actual["rows"]],
                )
                self.assertEqual(
                    [[(cell["row_span"], cell["column_span"]) for cell in row] for row in table_expected["rows"]],
                    [[(cell["row_span"], cell["column_span"]) for cell in row] for row in table_actual["rows"]],
                )
                self.assertTrue(all(
                    cell["fill"] == "D9E7F7" and cell["bold"]
                    for row in table_actual["rows"][:2] for cell in row
                ))

    @unittest.skipUnless(os.environ.get("IVT_RUN_POWERPOINT_SMOKE") == "1", "set IVT_RUN_POWERPOINT_SMOKE=1 to run PowerPoint smoke")
    def test_powerpoint_native_chart_and_table_smoke(self) -> None:
        artifacts = compile_reconstruction_plan(
            plan(), {"text_items": [{"id": "title-content", "text": "实验结果概览"}]}, request(),
            {"width_px": 1600, "height_px": 900}, structured_data(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary) / "work"
            iteration = work / "iterations" / "01"
            iteration.mkdir(parents=True)
            full_request = runtime_request("source.png")
            full_request["topic"] = "实验结果概览"
            (work / "request.json").write_text(json.dumps(full_request, ensure_ascii=False), encoding="utf-8")
            Image.new("RGB", (1600, 900), "#DDEEFF").save(work / "source.png")
            for name, document in artifacts.items():
                (iteration / f"{name}.json").write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable, str(SCRIPTS / "run_pipeline.py"), "--request", str(work / "request.json"),
                    "--iteration-dir", str(iteration), "--output-ppt", str(iteration / "p4-native-data.pptx"),
                    "--execution-mode", "diagnostic", "--renderer", "powerpoint", "--schema-dir", str(SCHEMAS),
                    "--run-id", "p4-native-data", "--iteration", "1",
                ], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240,
            )
            qa_path = iteration / "qa_report.json"
            evidence = qa_path.read_text(encoding="utf-8") if qa_path.is_file() else ""
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr + evidence)
            qa = json.loads(qa_path.read_text(encoding="utf-8"))
            self.assertEqual("1.4", qa["schema_version"])
            self.assertEqual("pass", qa["status"])
            self.assertEqual(0, qa["data_integrity"]["mismatch_count"])

            original_signatures = native_data_signatures(iteration / "p4-native-data.pptx")
            roundtrip_dir = iteration / "roundtrip"
            roundtrip_dir.mkdir()
            copy_path = roundtrip_dir / "input.pptx"
            saved_path = roundtrip_dir / "saved.pptx"
            state_path = roundtrip_dir / "state.json"
            shutil.copy2(iteration / "p4-native-data.pptx", copy_path)
            roundtrip = subprocess.run(
                [
                    sys.executable, str(SCRIPTS / "deck_roundtrip.py"), "--_worker", str(copy_path), str(saved_path),
                    str(roundtrip_dir / "render"), "1600", "900", str(state_path),
                ], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240,
            )
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
            self.assertEqual(0, roundtrip.returncode, roundtrip.stdout + roundtrip.stderr + str(state))
            self.assertEqual("passed", state.get("status"))
            self.assertEqual(original_signatures, native_data_signatures(saved_path))


if __name__ == "__main__":
    unittest.main()
