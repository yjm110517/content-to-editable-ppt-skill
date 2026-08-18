from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from canonical_artifact import canonical_sha256
from reconstruction_authority import build_reconstruction_asset_manifest, build_seed_view
from reconstruction_spec import compile_reconstruction_spec, validate_reconstruction_spec
from schema_utils import ContractError
from tests.runtime.test_p4_reconstruction_contracts import ReconstructionContractTests, approved_content, footprints, sha, visual_system, write, H


def seed_view(root: Path) -> dict:
    bundle = ReconstructionContractTests().authority(root)
    page = root / "S01"; asset = page / "visual.png"; Image.new("RGBA", (200, 200), (0, 0, 255, 255)).save(asset)
    record = {"schema_version":"1.0","artifact_type":"extracted_visual_asset_record","deck_id":"D01","slide_id":"S01","element_id":"EL-S01-V01","visual_ref":"S01-V01","approved_preview_sha256":bundle["pages"][0]["preview_record"]["final_preview_sha256"],"generated_layer_sha256":H,"element_map_sha256":canonical_sha256(bundle["pages"][0]["element_map"]),"crop_bbox":{"x":5200,"y":1800,"w":3500,"h":4500},"output_path":"visual.png","output_png_sha256":sha(asset),"background_removal_status":"clean_local_background","extraction_quality":"pass","status":"approved"}; write(page / "approved-extracted.json", record)
    manifest = build_reconstruction_asset_manifest(deck_id="D01", evidence_root=root, record_paths=[page / "approved-extracted.json"])
    system = visual_system()
    return build_seed_view(page=bundle["pages"][0], approved_content=approved_content(), visual_system=system, text_footprints=footprints(system), asset_manifest=manifest)


class ReconstructionSpecTests(unittest.TestCase):
    def test_projection_is_deterministic_and_zero_planner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            view = seed_view(Path(temporary)); first = compile_reconstruction_spec(view, order=1); second = compile_reconstruction_spec(view, order=1)
            self.assertEqual(first, second); self.assertEqual(validate_reconstruction_spec(first, view)["status"], "pass")
            self.assertEqual([item["element_id"] for item in first["elements"]], [item["element_id"] for item in sorted(view["seeds"], key=lambda item: (item["z_index"], item["element_id"]))])

    def test_order_changes_only_invalidate_sensitive_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            view = seed_view(Path(temporary)); a = compile_reconstruction_spec(view, order=1); b = compile_reconstruction_spec(view, order=8)
            self.assertEqual(a["page_input_sha256"], b["page_input_sha256"])
            one = compile_reconstruction_spec(view, order=1, order_sensitive=True, order_bindings=["slide_ordinal", "total_slide_count", "progress_fraction"], order_context={"slide_ordinal":1,"total_slide_count":10,"progress_fraction":"1/10"})
            eight = compile_reconstruction_spec(view, order=8, order_sensitive=True, order_bindings=["slide_ordinal", "total_slide_count", "progress_fraction"], order_context={"slide_ordinal":8,"total_slide_count":10,"progress_fraction":"8/10"})
            self.assertNotEqual(one["page_input_sha256"], eight["page_input_sha256"])
            with self.assertRaises(ContractError): compile_reconstruction_spec(view, order=1, order_sensitive=True, order_bindings=[], order_context={})

    def test_authority_class_text_and_full_slide_raster_tampering_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            view = seed_view(Path(temporary)); spec = compile_reconstruction_spec(view, order=1)
            changed = copy.deepcopy(spec); changed["elements"][0]["reconstruction_class"] = "decorative_approximation"
            self.assertEqual(validate_reconstruction_spec(changed, view)["status"], "blocking")
            text = copy.deepcopy(spec); item = next(value for value in text["elements"] if value["reconstruction_class"] == "native_text"); item["implementation"]["text"] = "tampered"
            self.assertIn("native_text_seed_incomplete", {issue["code"] for issue in validate_reconstruction_spec(text, view, allow_targeted_changes=True)["issues"]})
            raster = copy.deepcopy(spec); item = next(value for value in raster["elements"] if value["reconstruction_class"] == "reusable_raster"); item["normalized_bbox"] = {"x":0,"y":0,"w":10000,"h":10000}
            self.assertIn("full_slide_raster_substitution", {issue["code"] for issue in validate_reconstruction_spec(raster, view, allow_targeted_changes=True)["issues"]})

    def test_cli_compiles_and_validates_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); view = seed_view(root); write(root / "seed.json", view)
            script = str(SCRIPTS / "manage_reconstruction.py")
            compile_run = subprocess.run([sys.executable, script, "compile-spec", "--seed-view", str(root / "seed.json"), "--order", "1", "--output", str(root / "spec.json")], capture_output=True, text=True)
            self.assertEqual(compile_run.returncode, 0, compile_run.stdout + compile_run.stderr)
            validate_run = subprocess.run([sys.executable, script, "validate-spec", "--spec", str(root / "spec.json"), "--seed-view", str(root / "seed.json"), "--report", str(root / "report.json")], capture_output=True, text=True)
            self.assertEqual(validate_run.returncode, 0, validate_run.stdout + validate_run.stderr); self.assertEqual(json.loads((root / "report.json").read_text())["status"], "pass")


if __name__ == "__main__": unittest.main()
