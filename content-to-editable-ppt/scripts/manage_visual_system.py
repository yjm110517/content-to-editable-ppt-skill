from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, load_json, validate_schema
from visual_system_authority import SCHEMA_DIR, build_validation_report, freeze_visual_system, load_visual_system_authority
from visual_system_prompt import apply_correction, compile_prompt_package, compile_text_footprints
from visual_system_state import VisualSystemStateError, initial_state, record_host_pass, transition


def _bytes(value:dict)->bytes: return (json.dumps(value,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
def _write_once(path:Path,value:dict)->None:
    if path.exists(): raise ContractError([error(str(path),"immutable artifact already exists","overwrite_forbidden")])
    path.parent.mkdir(parents=True,exist_ok=True); temp=path.with_name(path.name+".tmp"); temp.write_bytes(_bytes(value)); os.replace(temp,path)
def _replace(path:Path,value:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True); temp=path.with_name(path.name+".tmp"); temp.write_bytes(_bytes(value)); os.replace(temp,path)
def _state(path:Path)->dict:
    value=load_json(path); validate_schema("visual_system_state",value,SCHEMA_DIR); return value
def _bundle(args:argparse.Namespace)->dict:
    return load_visual_system_authority(p1_state_path=args.p1_state.resolve(),deck_request_path=args.deck_request.resolve(),approved_outline_path=args.approved_outline.resolve(),slide_content_dir=args.slide_content_dir.resolve(),p2_state_path=args.p2_state.resolve(),wireframe_root=args.wireframe_root.resolve(),icon_asset_index_path=args.icon_asset_index.resolve())
def _authority_args(p:argparse.ArgumentParser)->None:
    p.add_argument("--p1-state",type=Path,required=True);p.add_argument("--deck-request",type=Path,required=True);p.add_argument("--approved-outline",type=Path,required=True);p.add_argument("--slide-content-dir",type=Path,required=True);p.add_argument("--p2-state",type=Path,required=True);p.add_argument("--wireframe-root",type=Path,required=True);p.add_argument("--icon-asset-index",type=Path,required=True)


def parser()->argparse.ArgumentParser:
    result=argparse.ArgumentParser(description="Manage P3.2 Deck Visual System and deterministic prompts"); sub=result.add_subparsers(dest="action",required=True)
    init=sub.add_parser("init");_authority_args(init);init.add_argument("--task-id",required=True);init.add_argument("--state",type=Path,required=True)
    submit=sub.add_parser("submit-candidate");_authority_args(submit);submit.add_argument("--state",type=Path,required=True);submit.add_argument("--candidate",type=Path,required=True);submit.add_argument("--validation-report",type=Path,required=True)
    correct=sub.add_parser("apply-correction");_authority_args(correct);correct.add_argument("--state",type=Path,required=True);correct.add_argument("--candidate",type=Path,required=True);correct.add_argument("--validation-report",type=Path,required=True);correct.add_argument("--correction",type=Path,required=True);correct.add_argument("--output-candidate",type=Path,required=True);correct.add_argument("--output-report",type=Path,required=True)
    freeze=sub.add_parser("freeze");_authority_args(freeze);freeze.add_argument("--state",type=Path,required=True);freeze.add_argument("--candidate",type=Path,required=True);freeze.add_argument("--output",type=Path,required=True)
    foot=sub.add_parser("compile-footprints");_authority_args(foot);foot.add_argument("--state",type=Path,required=True);foot.add_argument("--visual-system",type=Path,required=True);foot.add_argument("--output",type=Path,required=True)
    prompt=sub.add_parser("compile-prompts");_authority_args(prompt);prompt.add_argument("--state",type=Path,required=True);prompt.add_argument("--visual-system",type=Path,required=True);prompt.add_argument("--footprints",type=Path,required=True);prompt.add_argument("--previous-package",type=Path);prompt.add_argument("--package-output",type=Path,required=True);prompt.add_argument("--anchor-output",type=Path,required=True)
    verify=sub.add_parser("verify");verify.add_argument("--state",type=Path,required=True);verify.add_argument("--visual-system",type=Path,required=True);verify.add_argument("--footprints",type=Path,required=True);verify.add_argument("--prompt-package",type=Path,required=True);verify.add_argument("--anchor-request",type=Path,required=True)
    return result


def main()->int:
    args=parser().parse_args()
    try:
        if args.action=="init":
            bundle=_bundle(args); state=initial_state(args.task_id,bundle["deck_id"]); state=transition(state,"validating_authority"); state["current_artifacts"]["authority_bundle_sha256"]=bundle["authority_bundle_sha256"]; state=transition(state,"authority_validated",evidence=bundle["authority_bundle_sha256"]); state=transition(state,"visual_system_planning"); validate_schema("visual_system_state",state,SCHEMA_DIR); _write_once(args.state.resolve(),state); details={"authority_bundle_sha256":bundle["authority_bundle_sha256"]}
        elif args.action=="submit-candidate":
            state=_state(args.state.resolve()); bundle=_bundle(args); candidate=load_json(args.candidate.resolve()); report=build_validation_report(candidate,bundle,report_id=f"{candidate['artifact_id']}-validation",validated_at_utc=candidate["created_at_utc"]); _write_once(args.validation_report.resolve(),report); state=record_host_pass(state); state=transition(state,"candidate_ready",evidence=canonical_sha256(candidate)); state=transition(state,"validating_candidate",evidence=canonical_sha256(report)); state["current_artifacts"]["candidate_sha256"]=canonical_sha256(candidate);state["current_artifacts"]["validation_report_sha256"]=canonical_sha256(report);state=transition(state,{"pass":"visual_system_frozen","correctable":"contract_correction_required","blocking":"p3_2_failed"}[report["status"]]);_replace(args.state.resolve(),state);details={"validation_status":report["status"]}
        elif args.action=="apply-correction":
            state=_state(args.state.resolve());bundle=_bundle(args);candidate=load_json(args.candidate.resolve());report=load_json(args.validation_report.resolve());correction=load_json(args.correction.resolve());state=record_host_pass(state,correction=True);corrected=apply_correction(candidate,report,correction);new_report=build_validation_report(corrected,bundle,report_id=f"{corrected['artifact_id']}-correction-validation",validated_at_utc=correction["created_at_utc"]);_write_once(args.output_candidate.resolve(),corrected);_write_once(args.output_report.resolve(),new_report);state=transition(state,"validating_candidate",evidence=canonical_sha256(correction));state["current_artifacts"]["candidate_sha256"]=canonical_sha256(corrected);state["current_artifacts"]["validation_report_sha256"]=canonical_sha256(new_report);state=transition(state,{"pass":"visual_system_frozen","correctable":"p3_2_failed","blocking":"p3_2_failed"}[new_report["status"]]);_replace(args.state.resolve(),state);details={"validation_status":new_report["status"]}
        elif args.action=="freeze":
            state=_state(args.state.resolve());bundle=_bundle(args);candidate=load_json(args.candidate.resolve());
            if state["state"]!="visual_system_frozen" or canonical_sha256(candidate)!=state["current_artifacts"]["candidate_sha256"]: raise ContractError([error("$","freeze input does not match State","authority_hash_mismatch")])
            system=freeze_visual_system(candidate,bundle);_write_once(args.output.resolve(),system);state["revision"]=system["revision"];state["current_artifacts"]["deck_visual_system_sha256"]=canonical_sha256(system);_replace(args.state.resolve(),state);details={"deck_visual_system_sha256":canonical_sha256(system)}
        elif args.action=="compile-footprints":
            state=_state(args.state.resolve());bundle=_bundle(args);system=load_json(args.visual_system.resolve());
            if state["state"]!="visual_system_frozen" or canonical_sha256(system)!=state["current_artifacts"]["deck_visual_system_sha256"]: raise ContractError([error("$","footprint input does not match State","authority_hash_mismatch")])
            state=transition(state,"compiling_text_footprints");footprints=compile_text_footprints(system,bundle);_write_once(args.output.resolve(),footprints);state["current_artifacts"]["text_footprint_manifest_sha256"]=canonical_sha256(footprints);state=transition(state,"compiling_prompts",evidence=canonical_sha256(footprints));_replace(args.state.resolve(),state);details={"entries":len(footprints["entries"])}
        elif args.action=="compile-prompts":
            state=_state(args.state.resolve());bundle=_bundle(args);system=load_json(args.visual_system.resolve());footprints=load_json(args.footprints.resolve());previous=load_json(args.previous_package.resolve()) if args.previous_package else None
            if state["state"]!="compiling_prompts" or canonical_sha256(footprints)!=state["current_artifacts"]["text_footprint_manifest_sha256"]: raise ContractError([error("$","Prompt inputs do not match State","authority_hash_mismatch")])
            package,anchor=compile_prompt_package(system,footprints,bundle,previous);_write_once(args.package_output.resolve(),package);_write_once(args.anchor_output.resolve(),anchor);state["current_artifacts"]["deck_prompt_package_sha256"]=canonical_sha256(package);state["current_artifacts"]["style_anchor_request_sha256"]=canonical_sha256(anchor);state=transition(state,"style_anchor_ready",evidence=canonical_sha256(anchor));state=transition(state,"p3_2_complete");_replace(args.state.resolve(),state);details={"style_anchor_slide_id":anchor["slide_id"],"compiled_slides":len(package["slides"])}
        else:
            state=_state(args.state.resolve());system=load_json(args.visual_system.resolve());footprints=load_json(args.footprints.resolve());package=load_json(args.prompt_package.resolve());anchor=load_json(args.anchor_request.resolve());
            for kind,value in (("deck_visual_system",system),("text_footprint_manifest",footprints),("deck_prompt_package",package),("style_anchor_request",anchor)):validate_schema(kind,value,SCHEMA_DIR)
            expected=(canonical_sha256(system),canonical_sha256(footprints),canonical_sha256(package),canonical_sha256(anchor));actual=(state["current_artifacts"]["deck_visual_system_sha256"],state["current_artifacts"]["text_footprint_manifest_sha256"],state["current_artifacts"]["deck_prompt_package_sha256"],state["current_artifacts"]["style_anchor_request_sha256"])
            if state["state"]!="p3_2_complete" or expected!=actual:raise ContractError([error("$","P3.2 verification hash mismatch","authority_hash_mismatch")])
            details={"complete":True,"visual_quality_status":"not_evaluated"}
        print(json.dumps({"status":"ok","state":state["state"],**details},ensure_ascii=False));return 0
    except (ContractError,VisualSystemStateError,OSError,ValueError,KeyError,IndexError,json.JSONDecodeError) as exc:
        errors=exc.errors if isinstance(exc,ContractError) else [{"path":"$","code":"visual_system_error","message":str(exc)}];print(json.dumps({"status":"error","errors":errors},ensure_ascii=False));return 4


if __name__=="__main__":raise SystemExit(main())
