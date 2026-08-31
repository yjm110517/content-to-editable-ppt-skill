from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from asset_common import AssetError, sha256_file
from compile_reconstruction_plan import compile_to_iteration
from handoff_test_support import materializer_args
from materialize_reconstruction_handoff import materialize_handoff
from schema_utils import ContractError, validate_schema, validate_semantics
from shared_validator import validate_documents


def p1_plan() -> dict:
    return {
        "schema_version": "1.0",
        "page": {"id": "S01", "iteration": 1},
        "source": {"approved_design": "source.png"},
        "slide": {"width_in": 13.333, "height_in": 7.5, "background": "#FFFFFF"},
        "elements": [
            {
                "id": "title",
                "role": "title",
                "representation": "native_text",
                "geometry": {"coordinate_space": "normalized", "x": 0.05, "y": 0.05, "width": 0.4, "height": 0.1},
                "z_index": 20,
                "content_ref": "S01-title",
                "style": {"font_face": "Microsoft YaHei", "font_size_pt": 28, "color": "#102040"},
            },
            {
                "id": "card-01",
                "role": "card",
                "representation": "native_shape",
                "geometry": {"coordinate_space": "normalized", "x": 0.05, "y": 0.25, "width": 0.2, "height": 0.2},
                "z_index": 10,
                "style": {"shape": "roundRect", "fill": {"color": "#FFFFFF"}, "line": {"color": "#336699", "width_pt": 1}},
            },
            {
                "id": "card-02",
                "role": "card",
                "representation": "native_shape",
                "geometry": {"coordinate_space": "normalized", "x": 0.35, "y": 0.25, "width": 0.2, "height": 0.2},
                "z_index": 10,
                "style": {"shape": "roundRect", "fill": {"color": "#FFFFFF"}, "line": {"color": "#336699", "width_pt": 1}},
            },
            {
                "id": "connector",
                "role": "flow",
                "representation": "native_connector",
                "geometry": {"coordinate_space": "normalized", "x": 0.25, "y": 0.34, "width": 0.1, "height": 0.01},
                "z_index": 12,
                "from_id": "card-01",
                "to_id": "card-02",
                "style": {"line": {"color": "#336699", "width_pt": 1.5, "end_arrow": "triangle"}},
            },
            {
                "id": "hero",
                "role": "complex_visual",
                "representation": "raster_asset",
                "geometry": {"coordinate_space": "normalized", "x": 0.62, "y": 0.2, "width": 0.32, "height": 0.32},
                "z_index": 15,
                "asset_request": {
                    "source": "approved_design",
                    "source_region": {"coordinate_space": "normalized", "x": 0, "y": 0, "width": 1, "height": 1},
                    "contains_text": False,
                },
            },
        ],
    }


class ReconstructionHandoffTests(unittest.TestCase):
    def test_materializes_exact_files_and_deterministic_projections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = materializer_args(Path(temporary), SCHEMA_DIR, sha256_file)
            outputs = materialize_handoff(args)
            handoff = json.loads(Path(outputs["reconstruction_handoff"]).read_text(encoding="utf-8"))
            self.assertNotIn("status", handoff)
            self.assertEqual("source.png", handoff["stage2"]["approved_design"])
            self.assertEqual("S01-title", handoff["content"]["text_items"][0]["id"])
            stage1 = json.loads(args.stage1_authority.read_text(encoding="utf-8"))
            stage2 = json.loads(args.stage2_handoff.read_text(encoding="utf-8"))
            self.assertEqual(stage1["slides"][0]["wireframe"]["sha256"], sha256_file(Path(outputs["wireframe"])))
            self.assertEqual(stage2["slides"][0]["approved_design"]["sha256"], sha256_file(Path(outputs["approved_design"])))
            self.assertEqual(stage2["slides"][0]["visual_spec"]["sha256"], sha256_file(Path(outputs["visual_spec"])))
            first = {name: sha256_file(Path(outputs[name])) for name in ("source_content", "reconstruction_handoff")}
            args.force = True
            second_outputs = materialize_handoff(args)
            second = {name: sha256_file(Path(second_outputs[name])) for name in first}
            self.assertEqual(first, second)

    def test_reconstruction_handoff_schema_rejects_approval_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = materializer_args(Path(temporary), SCHEMA_DIR, sha256_file)
            outputs = materialize_handoff(args)
            candidate = json.loads(Path(outputs["reconstruction_handoff"]).read_text(encoding="utf-8"))
            candidate["status"] = "approved"
            with self.assertRaises(ContractError) as raised:
                validate_schema("reconstruction_handoff", candidate, SCHEMA_DIR)
            self.assertEqual("schema_error", raised.exception.errors[0]["code"])

    def test_reconstruction_handoff_rejects_unsafe_approved_design_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = materializer_args(Path(temporary), SCHEMA_DIR, sha256_file)
            outputs = materialize_handoff(args)
            base = json.loads(Path(outputs["reconstruction_handoff"]).read_text(encoding="utf-8"))
            for path in ("../source.png", "C:/source.png", "file://source.png", "https://example.com/source.png"):
                with self.subTest(path=path):
                    candidate = copy.deepcopy(base)
                    candidate["stage2"]["approved_design"] = path
                    validate_schema("reconstruction_handoff", candidate, SCHEMA_DIR)
                    with self.assertRaises(ContractError) as raised:
                        validate_semantics("reconstruction_handoff", candidate)
                    self.assertEqual("unsafe_path", raised.exception.errors[0]["code"])

    def test_default_collision_and_force(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = materializer_args(Path(temporary), SCHEMA_DIR, sha256_file)
            materialize_handoff(args)
            with self.assertRaises(AssetError) as raised:
                materialize_handoff(args)
            self.assertEqual("output_collision", raised.exception.detail["code"])
            args.force = True
            materialize_handoff(args)

    def test_force_rejects_non_file_destination_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = materializer_args(Path(temporary), SCHEMA_DIR, sha256_file)
            (args.work_root / "visual-spec.json").mkdir()
            args.force = True
            with self.assertRaises(AssetError) as raised:
                materialize_handoff(args)
            self.assertEqual("output_collision", raised.exception.detail["code"])
            self.assertFalse((args.work_root / "source-content.json").exists())

    def test_validation_failure_writes_no_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args = materializer_args(Path(temporary), SCHEMA_DIR, sha256_file)
            stage2 = json.loads(args.stage2_handoff.read_text(encoding="utf-8"))
            stage2["stage1_authority_sha256"] = "f" * 64
            args.stage2_handoff.write_text(json.dumps(stage2), encoding="utf-8")
            with self.assertRaises(AssetError) as raised:
                materialize_handoff(args)
            self.assertEqual("stage1_authority_stale", raised.exception.detail["code"])
            for name in ("source-content.json", "source.png", "wireframe.md", "visual-spec.json", "reconstruction-handoff.json"):
                self.assertFalse((args.work_root / name).exists())

    def test_authority_staleness_precedes_external_file_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = materializer_args(root, SCHEMA_DIR, sha256_file)
            stage2 = json.loads(args.stage2_handoff.read_text(encoding="utf-8"))
            stage2["stage1_authority_sha256"] = "f" * 64
            args.stage2_handoff.write_text(json.dumps(stage2), encoding="utf-8")
            (root / "stage2" / "designs" / "S01.png").unlink()
            with self.assertRaises(AssetError) as raised:
                materialize_handoff(args)
            self.assertEqual("stage1_authority_stale", raised.exception.detail["code"])

    def test_approved_file_hash_changes_are_blocked(self) -> None:
        mutations = (
            ("stage1/wireframes/S01.md", "wireframe_changed", b"changed"),
            ("stage2/designs/S01.png", "approved_design_changed", b"changed"),
            ("stage2/visual-specs/S01.json", "visual_spec_changed", b" "),
        )
        for relative, code, suffix in mutations:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                args = materializer_args(root, SCHEMA_DIR, sha256_file)
                with (root / relative).open("ab") as stream:
                    stream.write(suffix)
                with self.assertRaises(AssetError) as raised:
                    materialize_handoff(args)
                self.assertEqual(code, raised.exception.detail["code"])

    def test_missing_approved_files_are_blocked(self) -> None:
        missing = (
            ("stage1/wireframes/S01.md", "wireframe_changed"),
            ("stage2/designs/S01.png", "approved_design_changed"),
            ("stage2/visual-specs/S01.json", "visual_spec_changed"),
        )
        for relative, code in missing:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                args = materializer_args(root, SCHEMA_DIR, sha256_file)
                (root / relative).unlink()
                with self.assertRaises(AssetError) as raised:
                    materialize_handoff(args)
                self.assertEqual(code, raised.exception.detail["code"])

    def test_visual_spec_must_be_valid_json_object(self) -> None:
        for content in (b"not-json", b"[]"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                args = materializer_args(root, SCHEMA_DIR, sha256_file)
                spec_path = root / "stage2" / "visual-specs" / "S01.json"
                spec_path.write_bytes(content)
                stage2 = json.loads(args.stage2_handoff.read_text(encoding="utf-8"))
                stage2["slides"][0]["visual_spec"]["sha256"] = sha256_file(spec_path)
                args.stage2_handoff.write_text(json.dumps(stage2), encoding="utf-8")
                with self.assertRaises(AssetError) as raised:
                    materialize_handoff(args)
                self.assertEqual("invalid_visual_spec", raised.exception.detail["code"])

    def test_request_source_image_must_remain_inside_work_root(self) -> None:
        for source_image in ("../source.png", "C:/temp/source.png", "https://example.com/source.png", "file://source.png", "nested\\source.png"):
            with self.subTest(source_image=source_image), tempfile.TemporaryDirectory() as temporary:
                args = materializer_args(Path(temporary), SCHEMA_DIR, sha256_file, source_image=source_image)
                with self.assertRaises(AssetError) as raised:
                    materialize_handoff(args)
                self.assertEqual("unsafe_path", raised.exception.detail["code"])

    def test_p2_materializer_is_compatible_with_p1_compiler(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = materializer_args(root, SCHEMA_DIR, sha256_file)
            materialize_handoff(args)
            iteration = args.work_root / "iterations" / "01"
            iteration.mkdir(parents=True)
            plan_path = iteration / "reconstruction-plan.json"
            plan_path.write_text(json.dumps(p1_plan()), encoding="utf-8")
            compile_args = argparse.Namespace(
                plan=plan_path,
                content=args.work_root / "source-content.json",
                iteration_dir=iteration,
                schema_dir=SCHEMA_DIR,
                force=False,
            )
            outputs = compile_to_iteration(compile_args)
            documents = {
                "layout": json.loads(Path(outputs["layout"]).read_text(encoding="utf-8")),
                "crops": json.loads(Path(outputs["crops"]).read_text(encoding="utf-8")),
                "asset_manifest": json.loads(Path(outputs["asset_manifest"]).read_text(encoding="utf-8")),
            }
            validate_documents(documents, {kind: Path(path) for kind, path in outputs.items()}, profile="candidate", schema_dir=SCHEMA_DIR)


if __name__ == "__main__":
    unittest.main()
