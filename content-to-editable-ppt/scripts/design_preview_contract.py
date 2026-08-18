from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, validate_schema


SCHEMA_DIR=Path(__file__).resolve().parents[1]/"schemas"
CLASS_POLICY={
    "native_shape":(True,{"rebuild_from_element_map"}),"native_text":(True,{"reuse_authority_text_spec"}),"native_chart":(True,{"reuse_powerpoint_chart_spec"}),"sanitized_svg":(False,{"reuse_authority_asset"}),"reusable_raster":(False,{"extract_from_raw_layer"}),"generated_foreground":(False,{"extract_from_raw_layer"}),"generated_background":(False,{"reuse_background_raster","rebuild_background_from_style_tokens"}),"decorative_approximation":(False,{"approximate_from_style_tokens"})}
SHAPE_FIELDS={"shape_kind","fill","border","corner_radius","opacity","shadow_class"}


def validate_element_map(element_map:dict[str,Any],prompt_package:dict[str,Any],provisional_assets:list[dict[str,Any]]|None=None)->dict[str,Any]:
    validate_schema("design_element_map",element_map,SCHEMA_DIR);validate_schema("deck_prompt_package",prompt_package,SCHEMA_DIR)
    provisional_assets=provisional_assets or []
    for asset in provisional_assets:validate_schema("provisional_visual_asset_record",asset,SCHEMA_DIR)
    issues=[];elements=element_map["elements"];ids=[item["element_id"] for item in elements]
    if len(ids)!=len(set(ids)):issues.append(error("$.elements","Element IDs must be unique","duplicate_element_id"))
    slide=next((item for item in prompt_package["slides"] if item["slide_id"]==element_map["slide_id"]),None)
    if slide is None:issues.append(error("$.slide_id","Element Map slide is not in Prompt Package","unknown_slide"));intents=[]
    else:intents=slide["element_intents"]
    expected={item["future_element_map_id"] for item in intents};mapped={item["element_id"] for item in elements if not item["element_id"].startswith("GEN-")}
    if expected!=mapped:issues.append(error("$.elements","Every P3.2 Element Intent must map exactly once","element_intent_mismatch"))
    provisional_by_element={item["element_id"]:item for item in provisional_assets if item["extraction_quality"]=="pass"}
    counts={key:0 for key in CLASS_POLICY}
    for index,item in enumerate(elements):
        base=f"$.elements[{index}]";kind=item["reconstruction_class"];counts[kind]+=1;editable,strategies=CLASS_POLICY[kind]
        if item["editable_required"]!=editable:issues.append(error(base+".editable_required","Editability conflicts with Reconstruction Class","reconstruction_class_mismatch"))
        if item["p4_strategy"] not in strategies:issues.append(error(base+".p4_strategy","P4 Strategy conflicts with Reconstruction Class","reconstruction_class_mismatch"))
        box=item["normalized_bbox"]
        if box["x"]+box["w"]>10000 or box["y"]+box["h"]>10000:issues.append(error(base+".normalized_bbox","Element exceeds slide bounds","geometry_out_of_bounds"))
        if kind=="native_shape" and not SHAPE_FIELDS.issubset(item):issues.append(error(base,"Native Shape lacks reconstructable geometry/style","native_shape_incomplete"))
        if kind in {"reusable_raster","generated_foreground"} and item["element_id"] not in provisional_by_element:issues.append(error(base,"Raster element has no passing provisional extraction","raster_not_separable"))
        if kind=="generated_background" and item["p4_strategy"]=="reuse_background_raster" and any(other["reconstruction_class"]=="native_shape" for other in elements):issues.append(error(base,"Full background raster cannot be reused while native-required structures are baked in","raw_layer_reuse_forbidden"))
    audit=element_map["forbidden_generated_content"]
    if any(audit[key] for key in ("text_like_marks","logo_like_marks","unauthorized_labels","duplicate_resolved_icons","duplicate_chart_content")):issues.append(error("$.forbidden_generated_content","Generated Layer contains forbidden content","forbidden_generated_content"))
    if audit["unclassified_major_visual_count"]:issues.append(error("$.forbidden_generated_content.unclassified_major_visual_count","Major visuals remain unclassified","unclassified_major_visual"))
    if element_map["full_raw_layer_reuse_allowed"] and (counts["native_shape"] or counts["native_text"] or counts["native_chart"]):issues.append(error("$.full_raw_layer_reuse_allowed","Raw Layer reuse conflicts with native-required content","raw_layer_reuse_forbidden"))
    report={"schema_version":"1.0","artifact_type":"reconstruction_compatibility_report","deck_id":element_map["deck_id"],"slide_id":element_map["slide_id"],"element_map_sha256":canonical_sha256(element_map),"status":"fail" if issues else "pass","native_shape_count":counts["native_shape"],"native_text_count":counts["native_text"],"native_chart_count":counts["native_chart"],"sanitized_svg_count":counts["sanitized_svg"],"reusable_raster_count":counts["reusable_raster"],"generated_foreground_count":counts["generated_foreground"],"decorative_approximation_count":counts["decorative_approximation"],"unclassified_major_visual_count":audit["unclassified_major_visual_count"],"blocking_issues":[{"code":item["code"],"path":item["path"],"message":item["message"]} for item in issues]}
    validate_schema("reconstruction_compatibility_report",report,SCHEMA_DIR);return report


def require_compatible(element_map:dict[str,Any],prompt_package:dict[str,Any],provisional_assets:list[dict[str,Any]]|None=None)->dict[str,Any]:
    report=validate_element_map(element_map,prompt_package,provisional_assets)
    if report["status"]!="pass":raise ContractError([error(item["path"],item["message"],item["code"]) for item in report["blocking_issues"]])
    return report


def initial_state(deck_id:str)->dict[str,Any]:
    return {"schema_version":"1.0","artifact_type":"design_preview_state","deck_id":deck_id,"state":"p3_2_complete","budgets":{"initial_generation_per_slide":1,"technical_retry_per_stage":2,"map_pass_per_page":1,"map_correction_per_page":1},"counters":{"image_generation_calls":0,"automatic_regeneration_count":0,"full_deck_redesign_count":0,"host_map_pass_count":0,"map_correction_count":0,"planner_calls":0},"current_artifacts":{},"history":[]}


def transition(state:dict[str,Any],target:str,evidence:str|None=None)->dict[str,Any]:
    allowed={"p3_2_complete":{"validating_design_inputs"},"validating_design_inputs":{"anchor_generation_ready","p1_revision_required"},"anchor_generation_ready":{"anchor_generated"},"anchor_generated":{"anchor_mapping"},"anchor_mapping":{"reconstruction_compatibility_check"},"reconstruction_compatibility_check":{"reconstruction_incompatible","anchor_preview_building"},"anchor_preview_building":{"awaiting_anchor_confirmation"},"awaiting_anchor_confirmation":{"anchor_revision_requested","anchor_approved","p3_2_revision_required","p1_revision_required"},"anchor_approved":{"style_reference_ready"},"style_reference_ready":{"batch_generation_ready"},"batch_generation_ready":{"generating_pages"},"generating_pages":{"mapping_pages"},"mapping_pages":{"compatibility_checking_pages"},"compatibility_checking_pages":{"building_preview_powerpoints","reconstruction_incompatible"},"building_preview_powerpoints":{"contact_sheet_ready"},"contact_sheet_ready":{"awaiting_deck_confirmation"},"awaiting_deck_confirmation":{"page_revision_requested","p3_2_revision_required","p1_revision_required","design_previews_approved"},"design_previews_approved":{"promoting_extracted_assets"},"promoting_extracted_assets":{"p3_3_complete"}}
    if target not in allowed.get(state["state"],set()):raise ValueError(f"forbidden transition {state['state']} -> {target}")
    result=copy.deepcopy(state);result["history"].append({"from":state["state"],"to":target,"evidence":evidence});result["state"]=target;return result
