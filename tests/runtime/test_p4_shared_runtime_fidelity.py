from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from canonical_artifact import canonical_sha256
from reconstruction_authority import build_reconstruction_asset_manifest, build_seed_view
from reconstruction_qa import compare_visual_fidelity, inspect_reconstruction_page
from reconstruction_spec import compile_reconstruction_spec
from tests.runtime.test_p4_reconstruction_contracts import ReconstructionContractTests, approved_content, footprints, sha, visual_system, write, H


def build_inputs(root: Path) -> tuple[Path, Path, Path]:
    bundle = ReconstructionContractTests().authority(root); page = root / "S01"; asset = page / "visual.png"; Image.new("RGBA", (200, 200), (0, 90, 220, 255)).save(asset)
    record = {"schema_version":"1.0","artifact_type":"extracted_visual_asset_record","deck_id":"D01","slide_id":"S01","element_id":"EL-S01-V01","visual_ref":"S01-V01","approved_preview_sha256":bundle["pages"][0]["preview_record"]["final_preview_sha256"],"generated_layer_sha256":H,"element_map_sha256":canonical_sha256(bundle["pages"][0]["element_map"]),"crop_bbox":{"x":5200,"y":1800,"w":3500,"h":4500},"output_path":"visual.png","output_png_sha256":sha(asset),"background_removal_status":"clean_local_background","extraction_quality":"pass","status":"approved"}; write(page / "approved-extracted.json", record)
    manifest = build_reconstruction_asset_manifest(deck_id="D01", evidence_root=root, record_paths=[page / "approved-extracted.json"]); write(root / "asset-manifest.json", manifest)
    system = visual_system(); view = build_seed_view(page=bundle["pages"][0], approved_content=approved_content(), visual_system=system, text_footprints=footprints(system), asset_manifest=manifest); write(root / "seed.json", view)
    spec = compile_reconstruction_spec(view, order=1); write(root / "spec.json", spec)
    return root / "spec.json", root / "asset-manifest.json", root


class SharedRuntimeFidelityTests(unittest.TestCase):
    def test_reconstruction_page_uses_shared_native_builders_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); spec, manifest, evidence = build_inputs(root); node = os.environ.get("P3_TEST_NODE", "node"); script = str(SCRIPTS / "build_reconstruction_page.mjs")
            outputs = []
            for suffix in ("a", "b"):
                pptx = root / f"page-{suffix}.pptx"; report = root / f"report-{suffix}.json"
                run = subprocess.run([node, script, "--spec", str(spec), "--asset-manifest", str(manifest), "--evidence-root", str(evidence), "--output", str(pptx), "--report", str(report), "--python", sys.executable], capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr); outputs.append(pptx)
                qa = inspect_reconstruction_page(pptx_path=pptx, spec_path=spec, build_report_path=report); self.assertEqual(qa["status"], "pass", qa)
                with zipfile.ZipFile(pptx) as archive:
                    slide = archive.read("ppt/slides/slide1.xml").decode("utf-8"); self.assertIn("重建标题", slide); self.assertIn("ivt:GEN-S01-CARD", slide); self.assertNotIn("raw-generated-layer", slide)
            self.assertEqual(outputs[0].read_bytes(), outputs[1].read_bytes())

    def test_fidelity_metrics_are_anomaly_detectors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); approved = root / "approved.png"; same = root / "same.png"; opposite = root / "opposite.png"
            Image.new("RGB", (160, 90), "white").save(approved); Image.new("RGB", (160, 90), "white").save(same); Image.new("RGB", (160, 90), "black").save(opposite)
            self.assertEqual(compare_visual_fidelity(deck_id="D01", slide_id="S01", approved_preview=approved, candidate_render=same)["classification"], "pass")
            self.assertEqual(compare_visual_fidelity(deck_id="D01", slide_id="S01", approved_preview=approved, candidate_render=opposite)["classification"], "blocking_structural_drift")

    def test_powerpoint_render_path_is_available_for_optional_smoke(self) -> None:
        if os.environ.get("P4_COM_SMOKE") != "1": self.skipTest("PowerPoint COM smoke is gated")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); spec, manifest, evidence = build_inputs(root); pptx = root / "page.pptx"; report = root / "build.json"
            build = subprocess.run([os.environ.get("P3_TEST_NODE", "node"), str(SCRIPTS / "build_reconstruction_page.mjs"), "--spec", str(spec), "--asset-manifest", str(manifest), "--evidence-root", str(evidence), "--output", str(pptx), "--report", str(report), "--python", sys.executable], capture_output=True, text=True); self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            render = subprocess.run([sys.executable, str(SCRIPTS / "render_reconstruction_deck.py"), "--input", str(pptx), "--output-dir", str(root / "render"), "--report", str(root / "render.json"), "--width-px", "1600", "--height-px", "900"], capture_output=True, text=True); self.assertEqual(render.returncode, 0, render.stdout + render.stderr)


if __name__ == "__main__": unittest.main()
