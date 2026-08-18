from __future__ import annotations

import copy
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
from reconstruction_authority import file_sha256
from reconstruction_state import initial_page_state, record_targeted_patch, record_technical_retry
from reconstruction_workflow import apply_targeted_patch, compare_assembly, create_reconstruction_manifest, select_smoke_set
from schema_utils import ContractError
from tests.runtime.test_p4_shared_runtime_fidelity import build_inputs
from tests.runtime.test_p4_reconstruction_contracts import write, H


def page_entry(root: Path, spec_path: Path, slide_id: str, order: int) -> dict:
    page_pptx = root / f"{slide_id}.pptx"; page_pptx.write_bytes(b"page")
    render = root / f"{slide_id}.png"; Image.new("RGB", (160, 90), (order * 30, 50, 80)).save(render)
    return {"slide_id":slide_id,"order":order,"spec_path":spec_path.relative_to(root).as_posix(),"spec_sha256":file_sha256(spec_path),"page_pptx_path":page_pptx.relative_to(root).as_posix(),"page_pptx_sha256":file_sha256(page_pptx),"page_render_path":render.relative_to(root).as_posix(),"page_render_sha256":file_sha256(render),"order_sensitive":False,"reused":False}


class RecoveryDeckCandidateTests(unittest.TestCase):
    def test_smoke_set_uses_at_most_two_pages_for_class_coverage(self) -> None:
        specs = []
        for order, classes in enumerate((["native_text","native_shape"],["native_chart","sanitized_svg"],["reusable_raster","generated_foreground"]), 1):
            specs.append({"deck_id":"D01","slide_id":f"S{order:02d}","order":order,"elements":[{"reconstruction_class":kind} for kind in classes]})
        result = select_smoke_set(specs, ["S03"]); self.assertLessEqual(len(result["slide_ids"]), 2); self.assertTrue(result["production_fixture_required"]); self.assertIn("S03", result["slide_ids"])

    def test_targeted_patch_is_issue_bound_and_budgeted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); spec_path, _, _ = build_inputs(root); spec = json.loads(spec_path.read_text(encoding="utf-8")); seed = json.loads((root / "seed.json").read_text(encoding="utf-8")); index = next(i for i,item in enumerate(spec["elements"]) if item["reconstruction_class"]=="native_shape"); current = spec["elements"][index]["normalized_bbox"]["x"]
            issue = {"validation_issue_id":"P4-ISSUE-1","code":"bbox_alignment","path":f"$.elements[{index}].normalized_bbox","message":"align card","classification":"correctable"}; report={"schema_version":"1.0","artifact_type":"reconstruction_validation_report","deck_id":"D01","slide_id":"S01","spec_sha256":canonical_sha256(spec),"status":"targeted_patch_required","issues":[issue]}
            patch={"schema_version":"1.0","artifact_type":"reconstruction_patch","deck_id":"D01","slide_id":"S01","base_spec_sha256":canonical_sha256(spec),"patch_iteration":1,"operations":[{"validation_issue_id":"P4-ISSUE-1","op":"replace","path":f"/elements/{index}/normalized_bbox/x","before":current,"after":current+10}]}
            fixed=apply_targeted_patch(spec,seed,report,patch);self.assertEqual(fixed["elements"][index]["normalized_bbox"]["x"],current+10)
            forbidden=copy.deepcopy(patch);forbidden["operations"][0]["path"]=f"/elements/{index}/reconstruction_class"
            with self.assertRaises(ContractError):apply_targeted_patch(spec,seed,report,forbidden)
            state=initial_page_state("D01","S01");state=record_targeted_patch(state);state=record_targeted_patch(state)
            with self.assertRaises(ContractError):record_targeted_patch(state)
            retry=initial_page_state("D01","S01");retry=record_technical_retry(retry);retry=record_technical_retry(retry)
            with self.assertRaises(ContractError):record_technical_retry(retry)

    def test_multi_page_candidate_uses_shared_builder_and_is_delivery_forbidden(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);spec_path,asset_manifest,evidence=build_inputs(root);base=json.loads(spec_path.read_text(encoding="utf-8"));specs=[];entries=[]
            for order in (1,2):
                spec=copy.deepcopy(base);spec["slide_id"]=f"S{order:02d}";spec["order"]=order
                for element in spec["elements"]: element["element_id"]=element["element_id"].replace("S01",f"S{order:02d}")
                target=root/f"spec-{order}.json";write(target,spec);specs.append(target);entries.append(page_entry(root,target,spec["slide_id"],order))
            manifest=create_reconstruction_manifest(deck_id="D01",approved_manifest_sha256=H,asset_manifest_sha256=canonical_sha256(json.loads(asset_manifest.read_text(encoding="utf-8"))),pages=entries);write(root/"manifest.json",manifest)
            run=subprocess.run([os.environ.get("P3_TEST_NODE","node"),str(SCRIPTS/"build_reconstruction_deck.mjs"),"--manifest",str(root/"manifest.json"),"--reconstruction-root",str(root),"--asset-manifest",str(asset_manifest),"--evidence-root",str(evidence),"--output",str(root/"candidate.pptx"),"--report",str(root/"candidate.json"),"--python",sys.executable],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr);candidate=json.loads((root/"candidate.json").read_text());self.assertTrue(candidate["delivery_forbidden"]);self.assertEqual(candidate["slide_count"],2)
            with zipfile.ZipFile(root/"candidate.pptx") as archive:self.assertIn("ppt/slides/slide2.xml",archive.namelist())

    def test_assembly_comparison_requires_pixel_identical_page_renders(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);candidate=root/"candidate.pptx";candidate.write_bytes(b"candidate");spec=root/"spec.json";spec.write_text("{}")
            entries=[page_entry(root,spec,"S01",1),page_entry(root,spec,"S02",2)];manifest=create_reconstruction_manifest(deck_id="D01",approved_manifest_sha256=H,asset_manifest_sha256=H,pages=entries);write(root/"manifest.json",manifest)
            rendered=root/"assembled";rendered.mkdir();slides=[]
            for entry in entries:
                source=root/entry["page_render_path"];target=rendered/f"slide-{entry['order']:03d}.png";target.write_bytes(source.read_bytes());slides.append({"order":entry["order"],"path":target.name,"sha256":file_sha256(target)})
            report={"ppt_sha256":file_sha256(candidate),"slides":slides};write(root/"render.json",report)
            result=compare_assembly(manifest_path=root/"manifest.json",candidate_deck_path=candidate,candidate_render_report_path=root/"render.json",reconstruction_root=root,candidate_render_root=rendered);self.assertEqual(result["status"],"pass")
            Image.new("RGB",(160,90),"red").save(rendered/"slide-002.png");slides[1]["sha256"]=file_sha256(rendered/"slide-002.png");write(root/"render2.json",{"ppt_sha256":file_sha256(candidate),"slides":slides})
            result=compare_assembly(manifest_path=root/"manifest.json",candidate_deck_path=candidate,candidate_render_report_path=root/"render2.json",reconstruction_root=root,candidate_render_root=rendered);self.assertEqual(result["status"],"fail")

    def test_powerpoint_post_assembly_render_is_pixel_identical(self) -> None:
        if os.environ.get("P4_DECK_COM_SMOKE") != "1": self.skipTest("PowerPoint deck smoke is gated")
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);base_path,asset_manifest,evidence=build_inputs(root);base=json.loads(base_path.read_text(encoding="utf-8"));entries=[]
            for order in (1,2):
                spec=copy.deepcopy(base);spec["slide_id"]=f"S{order:02d}";spec["order"]=order
                for element in spec["elements"]:element["element_id"]=element["element_id"].replace("S01",spec["slide_id"])
                spec_path=root/f"spec-{order}.json";write(spec_path,spec);pptx=root/f"page-{order}.pptx";build_report=root/f"build-{order}.json"
                build=subprocess.run([os.environ.get("P3_TEST_NODE","node"),str(SCRIPTS/"build_reconstruction_page.mjs"),"--spec",str(spec_path),"--asset-manifest",str(asset_manifest),"--evidence-root",str(evidence),"--output",str(pptx),"--report",str(build_report),"--python",sys.executable],capture_output=True,text=True);self.assertEqual(build.returncode,0,build.stdout+build.stderr)
                render_dir=root/f"page-render-{order}";render_report=root/f"page-render-{order}.json";render=subprocess.run([sys.executable,str(SCRIPTS/"render_reconstruction_deck.py"),"--input",str(pptx),"--output-dir",str(render_dir),"--report",str(render_report),"--width-px","1600","--height-px","900"],capture_output=True,text=True);self.assertEqual(render.returncode,0,render.stdout+render.stderr)
                page_render=render_dir/"slide-001.png";entries.append({"slide_id":spec["slide_id"],"order":order,"spec_path":spec_path.relative_to(root).as_posix(),"spec_sha256":file_sha256(spec_path),"page_pptx_path":pptx.relative_to(root).as_posix(),"page_pptx_sha256":file_sha256(pptx),"page_render_path":page_render.relative_to(root).as_posix(),"page_render_sha256":file_sha256(page_render),"order_sensitive":False,"reused":False})
            manifest=create_reconstruction_manifest(deck_id="D01",approved_manifest_sha256=H,asset_manifest_sha256=canonical_sha256(json.loads(asset_manifest.read_text(encoding="utf-8"))),pages=entries);write(root/"manifest.json",manifest)
            candidate=root/"candidate.pptx";candidate_report=root/"candidate.json";build=subprocess.run([os.environ.get("P3_TEST_NODE","node"),str(SCRIPTS/"build_reconstruction_deck.mjs"),"--manifest",str(root/"manifest.json"),"--reconstruction-root",str(root),"--asset-manifest",str(asset_manifest),"--evidence-root",str(evidence),"--output",str(candidate),"--report",str(candidate_report),"--python",sys.executable],capture_output=True,text=True);self.assertEqual(build.returncode,0,build.stdout+build.stderr)
            candidate_render=root/"candidate-render";candidate_render_report=root/"candidate-render.json";render=subprocess.run([sys.executable,str(SCRIPTS/"render_reconstruction_deck.py"),"--input",str(candidate),"--output-dir",str(candidate_render),"--report",str(candidate_render_report),"--width-px","1600","--height-px","900"],capture_output=True,text=True);self.assertEqual(render.returncode,0,render.stdout+render.stderr)
            drift=compare_assembly(manifest_path=root/"manifest.json",candidate_deck_path=candidate,candidate_render_report_path=candidate_render_report,reconstruction_root=root,candidate_render_root=candidate_render);self.assertEqual(drift["status"],"pass",drift)


if __name__=="__main__":unittest.main()
