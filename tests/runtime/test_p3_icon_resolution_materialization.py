from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import os


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
SCHEMAS = ROOT / "content-to-editable-ppt" / "schemas"
VENDOR = ROOT / "content-to-editable-ppt" / "runtime" / "vendor" / "tabler-icons" / "3.46.0"
sys.path.insert(0, str(SCRIPTS))

import environment_preflight
from build_tabler_icon_index import build_index
from canonical_artifact import canonical_sha256
from markdown_wireframe import bind_markdown
from resolve_icon_asset import create_record, materialize, sha256_file, verify
from schema_utils import ContractError, validate_schema
from search_tabler_icons import rank
from validate_assets import validate_asset_set
from tests.runtime.test_p2_markdown_binder import MarkdownWireframeBinderTests, NOW, candidate


class IconResolutionMaterializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not VENDOR.is_dir():
            raise unittest.SkipTest("managed Tabler vendor copy has not been synchronized")
        cls.index = build_index(VENDOR)

    def fixture(self, root: Path, *, query: str = "code", icon_name: str = "code", method: str = "exact_canonical") -> dict[str, Path]:
        root.mkdir(parents=True, exist_ok=True)
        helper = MarkdownWireframeBinderTests()
        bundle = helper.bundle(root)
        markdown, manifest = bind_markdown(candidate(), bundle)
        manifest["status"] = "accepted"
        wireframe_root = root / "wireframes"
        wireframe_root.mkdir()
        (wireframe_root / "deck-wireframe.md").write_bytes(markdown)
        p2_manifest = wireframe_root / "wireframe-manifest.json"
        p2_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest_sha = canonical_sha256(manifest)
        direction = {
            "schema_version": "1.0", "artifact_type": "deck_visual_direction", "deck_id": "D01",
            "p2_manifest_sha256": manifest_sha, "icon_family": "tabler-outline", "created_at_utc": NOW,
        }
        direction_path = root / "visual-direction.json"
        direction_path.write_text(json.dumps(direction, ensure_ascii=False, indent=2), encoding="utf-8")
        evidence = rank(self.index, query, 8, visual_ref="S01-V01", p2_manifest_sha256=manifest_sha)
        evidence_path = root / "search-evidence.json"
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        record_path = root / "resolution-record.json"
        create_record(argparse.Namespace(
            p2_manifest=p2_manifest, wireframe_root=wireframe_root, visual_direction=direction_path,
            search_evidence=evidence_path, visual_ref="S01-V01", icon_name=icon_name,
            selection_method=method, vendor_root=VENDOR, created_at_utc=NOW, output=record_path,
        ))
        return {
            "p2_manifest": p2_manifest, "wireframe_root": wireframe_root, "direction": direction_path,
            "evidence": evidence_path, "record": record_path,
        }

    def materialize_fixture(self, root: Path) -> dict[str, Path]:
        paths = self.fixture(root)
        output_dir = root / "resolved" / "assets"
        materialize(argparse.Namespace(resolution_record=paths["record"], vendor_root=VENDOR, output_dir=output_dir))
        paths.update({
            "output_dir": output_dir,
            "manifest": output_dir.parent / "asset_manifest.json",
            "report": output_dir.parent / "svg_security_report.json",
            "consumption": output_dir.parent / "consumption-contract.json",
        })
        return paths

    def verify_args(self, paths: dict[str, Path]) -> argparse.Namespace:
        return argparse.Namespace(
            p2_manifest=paths["p2_manifest"], wireframe_root=paths["wireframe_root"],
            visual_direction=paths["direction"], search_evidence=paths["evidence"],
            resolution_record=paths["record"], vendor_root=VENDOR, asset_manifest=paths["manifest"],
            security_report=paths["report"], consumption_contract=paths["consumption"],
        )

    def test_record_binds_p2_direction_search_and_actual_vendor_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.fixture(Path(temporary))
            record = json.loads(paths["record"].read_text(encoding="utf-8"))
            self.assertEqual(record["source_sha256"], sha256_file(VENDOR / "icons" / "outline" / "code.svg"))
            self.assertEqual(record["search_evidence_sha256"], canonical_sha256(json.loads(paths["evidence"].read_text(encoding="utf-8"))))
            with self.assertRaises(ContractError):
                create_record(argparse.Namespace(
                    p2_manifest=paths["p2_manifest"], wireframe_root=paths["wireframe_root"], visual_direction=paths["direction"],
                    search_evidence=paths["evidence"], visual_ref="S01-V01", icon_name="code-ai", selection_method="host_from_top_k",
                    vendor_root=VENDOR, created_at_utc=NOW, output=Path(temporary) / "bad.json",
                ))

    def test_immutable_record_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.fixture(root)
            args = argparse.Namespace(
                p2_manifest=paths["p2_manifest"], wireframe_root=paths["wireframe_root"], visual_direction=paths["direction"],
                search_evidence=paths["evidence"], visual_ref="S01-V01", icon_name="code", selection_method="exact_canonical",
                vendor_root=VENDOR, created_at_utc=NOW, output=paths["record"],
            )
            with self.assertRaises(ContractError) as raised:
                create_record(args)
            self.assertIn("overwrite_forbidden", {item["code"] for item in raised.exception.errors})

    def test_materialization_uses_real_sanitizer_and_closes_hash_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.materialize_fixture(Path(temporary))
            result = verify(self.verify_args(paths))
            self.assertEqual(result["status"], "verified")
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            entry = manifest["assets"][0]
            self.assertEqual(entry["security_status"], "passed")
            self.assertEqual(entry["sha256"], entry["provenance"]["sanitized_svg_sha256"])
            report = json.loads(paths["report"].read_text(encoding="utf-8"))["results"][0]
            self.assertEqual(report["source_sha256"], entry["provenance"]["normalized_svg_sha256"])
            self.assertEqual(report["sanitized_sha256"], entry["sha256"])

    def test_same_input_materializes_to_identical_svg_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.materialize_fixture(root / "a")
            second = self.materialize_fixture(root / "b")
            self.assertEqual(
                (first["output_dir"] / "S01-V01.sanitized.svg").read_bytes(),
                (second["output_dir"] / "S01-V01.sanitized.svg").read_bytes(),
            )

    def test_authority_and_asset_tampering_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.materialize_fixture(Path(temporary))
            original = paths["wireframe_root"].joinpath("deck-wireframe.md").read_bytes()
            paths["wireframe_root"].joinpath("deck-wireframe.md").write_bytes(original + b"tamper")
            with self.assertRaises(ContractError):
                verify(self.verify_args(paths))
            paths["wireframe_root"].joinpath("deck-wireframe.md").write_bytes(original)
            svg = paths["output_dir"] / "S01-V01.sanitized.svg"
            svg.write_bytes(svg.read_bytes() + b"tamper")
            with self.assertRaises(ContractError) as raised:
                verify(self.verify_args(paths))
            self.assertIn("asset_integrity_mismatch", {item["code"] for item in raised.exception.errors})
            with self.assertRaises(Exception):
                validate_asset_set(
                    asset_dir=paths["output_dir"], manifest_path=paths["manifest"], schema_dir=SCHEMAS,
                    svg_report_path=paths["report"],
                )

    def test_builder_input_guard_rejects_sanitized_svg_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.materialize_fixture(Path(temporary))
            manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
            entry = manifest["assets"][0]
            svg = paths["output_dir"] / "S01-V01.sanitized.svg"
            svg.write_bytes(svg.read_bytes() + b"tamper")
            script = (
                "import {verifyResolvedAsset} from './content-to-editable-ppt/scripts/build_slide.mjs';"
                "try { await verifyResolvedAsset(JSON.parse(process.argv[1])); process.exit(0); }"
                "catch(e) { if(e.category==='hash_conflict') process.exit(9); throw e; }"
            )
            payload = {"id": entry["id"], "path": str(svg), "size_bytes": entry["size_bytes"], "sha256": entry["sha256"]}
            node = os.environ.get("P3_TEST_NODE", "node")
            completed = subprocess.run(
                [node, "--input-type=module", "-e", script, json.dumps(payload)],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 9, completed.stderr)

    def test_asset_manifest_13_remains_valid_and_14_raster_does_not_fake_svg_hashes(self) -> None:
        historical = {
            "schema_version": "1.3", "assets": [{
                "id": "A", "type": "png", "path": "assets/a.png", "source": "user-provided",
                "recolorable": False, "contains_text": False, "text_editability_exempt": False, "security_status": "passed",
            }],
        }
        validate_schema("asset_manifest", historical, SCHEMAS)
        raster = copy.deepcopy(historical)
        raster["schema_version"] = "1.4"
        raster["assets"][0]["source"] = "raster-handoff"
        raster["assets"][0]["provenance"] = {
            "provenance_type": "raster_handoff", "visual_ref": "S01-V01", "source_raster_sha256": "a" * 64,
        }
        validate_schema("asset_manifest", raster, SCHEMAS)

    @patch("environment_preflight.platform.system", return_value="Windows")
    @patch("environment_preflight.powerpoint_smoke_test")
    @patch("environment_preflight.command_ok", return_value=True)
    @patch("environment_preflight.resolve_executable")
    @patch("environment_preflight.command_version")
    @patch("environment_preflight.subprocess.run")
    def test_runtime_manifest_11_requires_actual_resvg_module_probe(self, run, version, resolve, command_ok, smoke, system) -> None:
        version.side_effect = ["Python 3.12.13", "v24.14.0"]
        resolve.side_effect = [Path(sys.executable), Path("C:/runtime/node.exe")]
        run.return_value = subprocess.CompletedProcess([], 0, "2.6.2\n", "")
        smoke.return_value = {"installed": True, "com_available": True, "smoke_test": "passed", "version": "16.0", "error": None}
        args = argparse.Namespace(
            python=Path(sys.executable), node=None, manifest=Path("unused"), skip_powerpoint_smoke=False,
            schema_dir=SCHEMAS, runtime_dir=SCRIPTS, require_svg_rasterizer=True,
        )
        manifest = environment_preflight.inspect_runtime(args)
        self.assertEqual(manifest["schema_version"], "1.1")
        self.assertTrue(manifest["tools"]["svg_rasterizer"]["available"])
        self.assertIn("import('@resvg/resvg-js')", run.call_args.args[0][-1])


if __name__ == "__main__":
    unittest.main()
