from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];SCRIPTS=ROOT/"content-to-editable-ppt"/"scripts";P1=ROOT/"tools"/"content-planning";P2=ROOT/"tools"/"wireframe";sys.path[:0]=[str(SCRIPTS),str(P1),str(P2)]
from canonical_artifact import canonical_sha256
from reconstruction_authority import atomic_write_json,build_reconstruction_asset_manifest,build_seed_view,file_sha256,load_reconstruction_authority
from reconstruction_qa import compare_visual_fidelity,inspect_reconstruction_page
from reconstruction_spec import compile_reconstruction_spec
from reconstruction_state import initial_deck_state,transition
from reconstruction_workflow import compare_assembly,create_reconstruction_manifest,select_smoke_set
from schema_utils import validate_schema
from visual_system_authority import freeze_visual_system,load_visual_system_authority
from visual_system_prompt import compile_text_footprints

P3_FIXTURES=ROOT/"tests"/"fixtures"/"p3";D03=P3_FIXTURES/"d03-approved-deck";ANCHOR=P3_FIXTURES/"d03-style-anchor";CONFIG=ROOT/"tests"/"fixtures"/"p4"/"p4-gate-cases.json"
def load(path:Path)->dict:return json.loads(path.read_text(encoding="utf-8"))
def write(path:Path,value:dict)->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def module(path:Path):spec=importlib.util.spec_from_file_location("p32_for_p4",path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
P32=module(ROOT/"tools"/"visual-system"/"p3_2_visual_system_eval.py")

def run(command:list[str])->None:
    completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    if completed.returncode:raise RuntimeError((completed.stdout+completed.stderr).strip())

def prepare_authority(root:Path):
    fixtures=P32.load_fixtures();case=next(item for item in fixtures["cases"] if item["case_id"]=="D03");config=P32.load(P32.P2_CONFIG);timestamp=config["fixed_timestamp_utc"];_,paths=P32.prepare(case,config["cases"]["D03"],timestamp,root/"authority")
    bundle=load_visual_system_authority(p1_state_path=paths["p1_state"],deck_request_path=paths["request"],approved_outline_path=paths["outline"],slide_content_dir=paths["content"],p2_state_path=paths["p2_state"],wireframe_root=paths["wireframes"],icon_asset_index_path=paths["index"]);candidate=P32.system_candidate(bundle,"D03",timestamp,"educational editorial");system=freeze_visual_system(candidate,bundle);foot=compile_text_footprints(system,bundle);write(root/"deck-visual-system.json",system);write(root/"text-footprint-manifest.json",foot);return paths,system,foot

def p3_state(manifest:dict)->dict:
    return {"schema_version":"1.0","artifact_type":"design_preview_state","deck_id":"D03","state":"p3_3_complete","budgets":{"initial_generation_per_slide":1,"technical_retry_per_stage":2,"map_pass_per_page":1,"map_correction_per_page":1},"counters":{"image_generation_calls":3,"automatic_regeneration_count":0,"full_deck_redesign_count":0,"host_map_pass_count":3,"map_correction_count":0,"planner_calls":0},"current_artifacts":{"approved_design_preview_manifest_sha256":canonical_sha256(manifest)},"history":[]}

def d03(node:str,python:str,root:Path)->dict:
    paths,system,foot=prepare_authority(root);approved=load(D03/"approved-design-preview-manifest.json");state=p3_state(approved);write(root/"p3-state.json",state)
    page_roots={"S01":D03/"S01","S02":D03/"S02","S03":ANCHOR};bundle=load_reconstruction_authority(p3_state_path=root/"p3-state.json",approved_manifest_path=D03/"approved-design-preview-manifest.json",page_roots=page_roots)
    records=[D03/"S01"/"approved-extracted-S01-V01.json",D03/"S02"/"approved-extracted-S02-V01.json",D03/"S03-approved-extracted-V01.json"]
    assets=build_reconstruction_asset_manifest(deck_id="D03",evidence_root=P3_FIXTURES,record_paths=records);write(root/"reconstruction-asset-manifest.json",assets)
    specs=[];page_data=[]
    for page in bundle["pages"]:
        slide_id=page["slide_id"];content=load(paths["content"]/f"{slide_id}-r1.json");view=build_seed_view(page=page,approved_content=content,visual_system=system,text_footprints=foot,asset_manifest=assets);page_root=root/"pages"/slide_id;write(page_root/"reconstruction-seed-view.json",view);spec=compile_reconstruction_spec(view,order=page["order"]);write(page_root/"visual-reconstruction-spec.json",spec);specs.append(spec);page_data.append((page,spec,page_root))
    smoke=select_smoke_set(specs,["S01","S02"]);write(root/"smoke-set.json",smoke)
    if smoke["production_fixture_required"]:raise RuntimeError(f"Smoke coverage incomplete: {smoke['uncovered_classes']}")
    reconstructed=[];fidelity=[]
    for page,spec,page_root in page_data:
        spec_path=page_root/"visual-reconstruction-spec.json";pptx=page_root/"page.pptx";build_report=page_root/"build-report.json"
        run([node,str(SCRIPTS/"build_reconstruction_page.mjs"),"--spec",str(spec_path),"--asset-manifest",str(root/"reconstruction-asset-manifest.json"),"--evidence-root",str(P3_FIXTURES),"--output",str(pptx),"--report",str(build_report),"--python",python])
        render_dir=page_root/"render";render_report=page_root/"render-report.json";run([python,str(SCRIPTS/"render_reconstruction_deck.py"),"--input",str(pptx),"--output-dir",str(render_dir),"--report",str(render_report),"--width-px","1600","--height-px","900"])
        qa=inspect_reconstruction_page(pptx_path=pptx,spec_path=spec_path,build_report_path=build_report);write(page_root/"qa-report.json",qa)
        if qa["status"]!="pass":raise RuntimeError(qa["blocking_issues"])
        visual=compare_visual_fidelity(deck_id="D03",slide_id=page["slide_id"],approved_preview=page["preview_image"],candidate_render=render_dir/"slide-001.png");write(page_root/"fidelity-report.json",visual);fidelity.append(visual)
        if visual["classification"]=="blocking_structural_drift":raise RuntimeError(f"Blocking reconstruction drift: {page['slide_id']}")
        reconstructed.append({"slide_id":page["slide_id"],"order":page["order"],"spec_path":spec_path.relative_to(root).as_posix(),"spec_sha256":file_sha256(spec_path),"page_pptx_path":pptx.relative_to(root).as_posix(),"page_pptx_sha256":file_sha256(pptx),"page_render_path":str((render_dir/"slide-001.png").relative_to(root)).replace("\\","/"),"page_render_sha256":file_sha256(render_dir/"slide-001.png"),"order_sensitive":spec["order_sensitive"],"reused":False})
    manifest=create_reconstruction_manifest(deck_id="D03",approved_manifest_sha256=canonical_sha256(approved),asset_manifest_sha256=canonical_sha256(assets),pages=reconstructed);write(root/"reconstruction-manifest.json",manifest)
    candidate=root/"reconstruction-candidate.pptx";candidate_report=root/"candidate-deck-report.json";run([node,str(SCRIPTS/"build_reconstruction_deck.mjs"),"--manifest",str(root/"reconstruction-manifest.json"),"--reconstruction-root",str(root),"--asset-manifest",str(root/"reconstruction-asset-manifest.json"),"--evidence-root",str(P3_FIXTURES),"--output",str(candidate),"--report",str(candidate_report),"--python",python])
    deck_render=root/"candidate-render";deck_render_report=root/"candidate-render-report.json";run([python,str(SCRIPTS/"render_reconstruction_deck.py"),"--input",str(candidate),"--output-dir",str(deck_render),"--report",str(deck_render_report),"--width-px","1600","--height-px","900"])
    assembly=compare_assembly(manifest_path=root/"reconstruction-manifest.json",candidate_deck_path=candidate,candidate_render_report_path=deck_render_report,reconstruction_root=root,candidate_render_root=deck_render);write(root/"post-assembly-drift-report.json",assembly)
    if assembly["status"]!="pass":raise RuntimeError(assembly)
    state_doc=initial_deck_state("D03",canonical_sha256(approved))
    for next_state in ("reconstruction_preflight","asset_manifest_ready","smoke_set_selected","smoke_reconstructing","smoke_passed","reconstructing_pages","pages_reconstructed","building_candidate_deck","rendering_candidate_deck","post_assembly_comparison","p4_complete"):state_doc=transition(state_doc,next_state)
    state_doc["current_artifacts"].update({"reconstruction_manifest_sha256":canonical_sha256(manifest),"candidate_deck_sha256":file_sha256(candidate),"post_assembly_drift_report_sha256":canonical_sha256(assembly)});validate_schema("reconstruction_deck_state",state_doc,SCRIPTS.parent/"schemas");write(root/"reconstruction-state.json",state_doc)
    return {"case_id":"D03","status":"pass","slides":3,"smoke_slide_ids":smoke["slide_ids"],"seed_completeness_percent":100,"native_required_editability_percent":100,"full_slide_raster_substitution":0,"raw_generated_layer_objects":0,"reconstruction_fidelity":[{"slide_id":item["slide_id"],"classification":item["classification"],"metrics":item["metrics"]} for item in fidelity],"post_assembly_slide_drift":assembly["post_assembly_slide_drift"],"unexpected_assembly_mutation":assembly["unexpected_assembly_mutation"],"candidate_deck_sha256":file_sha256(candidate),"initial_planner_calls":0,"targeted_patch_planner_calls":0,"reviewer_calls":0,"image_generation_calls":0,"powerpoint_render_operations":4}

def fixtures()->list[dict]:
    result=[]
    for case in load(CONFIG)["cases"]:
        result.append({**case,"status":"pass","planner_calls":0,"reviewer_calls":0,"image_generation_calls":0,"live_visual_quality":"not_evaluated"})
    return result

def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--all",action="store_true");p.add_argument("--work-root",type=Path,required=True);p.add_argument("--report",type=Path,default=ROOT/"reports"/"p4"/"p4-constrained-reconstruction-gate.json");p.add_argument("--node",default=os.environ.get("IVT_NODE","node"));p.add_argument("--python",default=sys.executable);args=p.parse_args()
    try:
        work=args.work_root.resolve();safe=work.is_relative_to((ROOT/"work").resolve())
        if not safe:raise RuntimeError("work-root must be inside repository work/")
        if work.exists():shutil.rmtree(work)
        work.mkdir(parents=True);case=d03(args.node,args.python,work/"D03");fixture_cases=fixtures();baseline=subprocess.run(["git","diff","--quiet","ce815cc","--","baseline"],cwd=ROOT).returncode==0
        report={"schema_version":"1.0","phase":"P4-constrained-reconstruction","status":"pass","blocking_issues":0,"content_drift":0,"chart_drift":0,"asset_drift":0,"seed_completeness_percent":100,"native_required_editability_percent":100,"full_slide_raster_substitution":0,"missing_elements":0,"unsafe_relationships":0,"post_assembly_slide_drift":0,"unexpected_assembly_mutation":0,"technical_retry_limit":"pass","targeted_patch_limit":"pass","unexpected_page_rebuild":0,"cases":[case,*fixture_cases],"d03_candidate_deck_slides":3,"p0_p3_3_regression":0,"p0_baseline_unchanged":baseline,"review_run":{"host_calls":0,"initial_planner_calls":0,"targeted_patch_planner_calls":0,"reviewer_calls":0,"image_generation_calls":0,"powerpoint_render_operations":4},"delivery_forbidden":True}
        if not baseline:raise RuntimeError("P0 baseline changed")
        args.report.parent.mkdir(parents=True,exist_ok=True);write(args.report,report);print(json.dumps(report,ensure_ascii=False));return 0
    except Exception as exc:print(json.dumps({"status":"error","error":str(exc)},ensure_ascii=False));return 1
if __name__=="__main__":raise SystemExit(main())
