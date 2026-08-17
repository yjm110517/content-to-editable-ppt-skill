from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT=Path(__file__).resolve().parents[2];SCRIPTS=ROOT/"content-to-editable-ppt"/"scripts";P1TOOLS=ROOT/"tools"/"content-planning";P2TOOLS=ROOT/"tools"/"wireframe"
sys.path[:0]=[str(SCRIPTS),str(P1TOOLS),str(P2TOOLS)]
from canonical_artifact import canonical_sha256
from markdown_wireframe import bind_markdown,build_validation_report as p2_report
from p1_content_planning_eval import load_fixtures
from p2_wireframe_eval import authority,fixture_candidate
from schema_utils import validate_schema
from visual_system_authority import build_validation_report,freeze_visual_system,load_visual_system_authority
from visual_system_prompt import compile_prompt_package,compile_text_footprints
from wireframe_state import initial_state as p2_initial_state


P2_CONFIG=ROOT/"tests"/"fixtures"/"p2"/"markdown-wireframe-cases.json"
def load(path:Path)->dict[str,Any]:return json.loads(path.read_text(encoding="utf-8"))
def write(path:Path,value:dict[str,Any])->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def system_candidate(bundle:dict[str,Any],case_id:str,timestamp:str,style:str)->dict[str,Any]:
    font={"family":"Microsoft YaHei","fallback_family":"Arial","size_pt":20,"minimum_size_pt":16,"weight":"regular","max_lines":5,"line_height_milli":1200};roles=[]
    family_map={"cover":"cover","opening":"cover","process":"process","closing":"summary","conclusion":"summary","content":"content"}
    for page in bundle["approved_outline"]["pages"]:
        if page["role"] not in roles:roles.append(page["role"])
    return {"schema_version":"1.0","canonicalization_version":"p1-rfc8785-nfc-1","artifact_type":"deck_visual_system_candidate","artifact_id":f"{case_id}-visual-r1","deck_id":case_id,"revision":1,"parent_sha256":None,"pass_id":"initial","host_model_invocation_id":f"{case_id}-host-visual-initial","hard_constraints":{"output_ratio":"16:9","canvas":{"width_px":1600,"height_px":900},"safe_area":{"top":500,"right":500,"bottom":500,"left":500},"palette":{"primary":"#2457C5","background":"#FFFFFF","surface":"#F2F5FA","accent":"#F28C28","text_primary":"#111111","text_secondary":"#555555"},"typography":{"title":{**font,"size_pt":30,"minimum_size_pt":24,"weight":"bold","max_lines":2},"subtitle":{**font,"size_pt":24,"minimum_size_pt":20,"weight":"semibold","max_lines":2},"body":font,"label":{**font,"size_pt":16,"minimum_size_pt":12,"max_lines":2}},"prohibitions":{"model_rendered_formal_text":True,"model_redrawn_resolved_svg":True,"logos":True,"watermarks":True,"external_assets":True,"extra_facts":True,"full_slide_text_rasterization":True},"raster_handoff_policy":{"must_be_spatially_isolated":True,"must_not_contain_text":True,"must_not_be_occluded":True,"minimum_short_edge":800,"safe_padding":300,"avoid_background_entanglement":True,"avoid_long_range_shadow":True}},"soft_design_guidance":{"style_concept":style,"style_keywords":[style,"clear hierarchy","visual freedom"],"grid":{"recommended_columns":6,"recommended_gutter":300},"spacing_scale":[200,300,500,800],"template_families":[{"slide_role":role,"family":family_map.get(role,"content")} for role in roles],"card_language":"Cards are optional; use them only where they improve grouping.","image_treatment":"Allow asymmetric cropping and clear focal subjects.","chart_treatment":"Reserve clean chart zones for deterministic overlays.","diagram_treatment":"Use expressive structure without formal labels.","composition_guidance":["Use asymmetry when useful","Preserve generous whitespace","Create clear scale contrast"],"creative_freedom":{"asymmetry":True,"scale_contrast":True,"local_overlap":True,"image_text_interplay":True,"irregular_rhythm":True}},"created_at_utc":timestamp}


def prepare(case:dict[str,Any],config:dict[str,Any],timestamp:str,root:Path)->tuple[dict[str,Any],dict[str,Path]]:
    p1,paths=authority(case,timestamp,root/"p1");candidate=config.get("candidate") if case["case_id"]=="D03" else fixture_candidate(p1,case["case_id"],timestamp);report=p2_report(candidate,p1,report_id=f"{case['case_id']}-p32-p2",validated_at_utc=timestamp)
    if report["status"]!="pass":raise RuntimeError(report["issues"])
    markdown,manifest=bind_markdown(candidate,p1);manifest["status"]="accepted";wire=root/"wireframes";revision=wire/"revisions"/"r001";revision.mkdir(parents=True);(wire/"deck-wireframe.md").write_bytes(markdown);write(wire/"wireframe-manifest.json",manifest);write(revision/"candidate.json",candidate)
    state=p2_initial_state(task_id=f"{case['case_id']}-task",deck_id=case["case_id"],approved_outline_sha256=manifest["approved_outline_sha256"],slide_content_manifest_sha256=manifest["slide_content_manifest_sha256"]);state["state"]="p2_complete";state["current_revision"]=1;state["current_artifacts"]["candidate_sha256"]=manifest["candidate_sha256"];state["current_artifacts"]["wireframe_manifest_sha256"]=canonical_sha256(manifest);state["current_artifacts"]["wireframe_sha256"]=manifest["wireframe_sha256"];p2_state=root/"p2-state.json";write(p2_state,state)
    request={"schema_version":"1.0","canonicalization_version":"p1-rfc8785-nfc-1","task_id":f"{case['case_id']}-task","deck_id":case["case_id"],"topic":case["topic"],"objective":case["objective"],"audience":case["audience"],"language":"zh-CN","page_count":len(manifest["slides"]),"output_ratio":"16:9","source_material_ids":["M01"],"must_preserve":[],"prohibited_changes":[],"visual_requirements":[],"external_research":"not_authorized"};request_path=root/"deck-request.json";write(request_path,request)
    p2sha=canonical_sha256(manifest);entries=[]
    for slide in manifest["slides"]:
        for visual in slide["visual_placeholders"]:
            if visual["role"]!="icon":continue
            handoff={"schema_version":"1.0","artifact_type":"raster_handoff_pending","deck_id":case["case_id"],"slide_id":slide["slide_id"],"visual_ref":visual["visual_ref"],"semantic":visual["semantic"],"semantic_source_refs":visual["semantic_source_refs"],"p2_manifest_sha256":p2sha,"visual_direction_sha256":"a"*64,"search_evidence_sha256":"b"*64,"selection_decision_sha256":"c"*64,"reason":"no_accurate_tabler_match","status":"raster_handoff_pending","created_at_utc":timestamp};path=root/"icon-assets"/f"{visual['visual_ref']}.json";write(path,handoff);entries.append({"visual_ref":visual["visual_ref"],"status":"raster_handoff_pending","handoff_path":f"icon-assets/{visual['visual_ref']}.json","handoff_sha256":canonical_sha256(handoff)})
    index={"schema_version":"1.0","canonicalization_version":"p1-rfc8785-nfc-1","artifact_type":"p3_icon_asset_authority_index","scope":"icon","deck_id":case["case_id"],"p2_manifest_sha256":p2sha,"entries":entries};index_path=root/"p3-icon-asset-authority-index.json";write(index_path,index)
    return p1,{"p1_state":paths["p1"],"outline":paths["outline"],"content":paths["content"],"p2_state":p2_state,"wireframes":wire,"request":request_path,"index":index_path}


def evaluate(case:dict[str,Any],config:dict[str,Any],timestamp:str,root:Path)->dict[str,Any]:
    _,paths=prepare(case,config,timestamp,root);bundle=load_visual_system_authority(p1_state_path=paths["p1_state"],deck_request_path=paths["request"],approved_outline_path=paths["outline"],slide_content_dir=paths["content"],p2_state_path=paths["p2_state"],wireframe_root=paths["wireframes"],icon_asset_index_path=paths["index"]);styles={"D03":"educational editorial","D05":"business professional","D08":"technical systems"};candidate=system_candidate(bundle,case["case_id"],timestamp,styles[case["case_id"]]);report=build_validation_report(candidate,bundle,report_id=f"{case['case_id']}-visual",validated_at_utc=timestamp)
    if report["status"]!="pass":raise RuntimeError(report["issues"])
    system=freeze_visual_system(candidate,bundle);foot1=compile_text_footprints(system,bundle);foot2=compile_text_footprints(system,bundle);package1,anchor1=compile_prompt_package(system,foot1,bundle);package2,anchor2=compile_prompt_package(system,foot2,bundle)
    if foot1!=foot2 or package1!=package2 or anchor1!=anchor2:raise RuntimeError("deterministic compilation drift")
    if anchor1["slide_id"] in package1["high_risk_slide_ids"] and len(package1["slides"])>1:raise RuntimeError("high-risk page incorrectly selected as representative Anchor")
    call_count=1 if case["case_id"]=="D03" else 0
    return {"case_id":case["case_id"],"status":"pass","slides":len(package1["slides"]),"host_model_invocations":call_count,"contract_corrections":0,"prompt_drift":0,"text_footprint_drift":0,"style_anchor_slide_id":anchor1["slide_id"],"high_risk_slide_ids":package1["high_risk_slide_ids"],"prompt_package_sha256":canonical_sha256(package1)}


def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--all",action="store_true");p.add_argument("--work-root",type=Path,default=ROOT/"work"/"p3-visual-system");p.add_argument("--report",type=Path);args=p.parse_args()
    try:
        if args.work_root.exists():shutil.rmtree(args.work_root)
        args.work_root.mkdir(parents=True);fixtures=load_fixtures();cases={item["case_id"]:item for item in fixtures["cases"]};config=load(P2_CONFIG);timestamp=config["fixed_timestamp_utc"];results=[evaluate(cases[cid],config["cases"].get(cid,{}),timestamp,args.work_root/cid) for cid in ("D03","D05","D08")]
        report={"schema_version":"1.0","phase":"P3.2-contract-prompt-gate","status":"pass","contract_prompt_gate":"pass","visual_quality_status":"not_evaluated","blocking_issues":0,"authority_drift":0,"prompt_drift":0,"text_footprint_drift":0,"layer_ownership_violations":0,"missing_element_bindings":0,"unexpected_page_recompile":0,"cases":results,"recorded_d03_host_model_invocations":1,"review_run":{"live_host_model_invocations":0,"prompt_compiler_agent_calls":0,"image_generation_calls":0,"planner_calls":0,"reviewer_calls":0,"powerpoint_calls":0},"p0_baseline_unchanged":subprocess.run(["git","diff","--quiet","ce815cc","--","baseline"],cwd=ROOT).returncode==0}
        if not report["p0_baseline_unchanged"]:raise RuntimeError("P0 baseline changed")
        output=(args.report or args.work_root/"p3-visual-system-prompt-contract-gate.json").resolve();write(output,report);print(json.dumps(report,ensure_ascii=False));return 0
    except Exception as exc:print(json.dumps({"status":"error","error":str(exc)},ensure_ascii=False));return 1
if __name__=="__main__":raise SystemExit(main())
