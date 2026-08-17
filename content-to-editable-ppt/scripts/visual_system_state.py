from __future__ import annotations

import copy
from typing import Any


class VisualSystemStateError(RuntimeError):
    pass


def initial_state(task_id: str, deck_id: str) -> dict[str, Any]:
    return {"schema_version":"1.0","artifact_type":"visual_system_state","task_id":task_id,"deck_id":deck_id,"state":"received","revision":0,"budgets":{"max_contract_corrections_per_pass":1,"max_host_invocations_per_pass":2},"counters":{"host_initial_pass_count":0,"host_revision_pass_count":0,"host_contract_correction_count":0,"host_model_invocation_count":0,"current_pass_corrections":0,"automatic_visual_redesign_count":0,"prompt_compiler_agent_calls":0,"image_generation_calls":0,"planner_calls":0,"reviewer_calls":0,"powerpoint_calls":0},"current_artifacts":{"authority_bundle_sha256":None,"candidate_sha256":None,"validation_report_sha256":None,"deck_visual_system_sha256":None,"text_footprint_manifest_sha256":None,"deck_prompt_package_sha256":None,"style_anchor_request_sha256":None},"changed_slide_ids":[],"history":[]}


def transition(state: dict[str, Any], target: str, *, evidence: str | None = None) -> dict[str, Any]:
    allowed={"received":{"validating_authority"},"validating_authority":{"authority_validated","p3_2_failed"},"authority_validated":{"visual_system_planning"},"visual_system_planning":{"candidate_ready","p3_2_failed"},"candidate_ready":{"validating_candidate"},"validating_candidate":{"contract_correction_required","visual_system_frozen","p3_2_failed"},"contract_correction_required":{"validating_candidate","p3_2_failed"},"visual_system_frozen":{"compiling_text_footprints"},"compiling_text_footprints":{"compiling_prompts","p3_2_failed"},"compiling_prompts":{"style_anchor_ready","p3_2_failed"},"style_anchor_ready":{"p3_2_complete"}}
    if target not in allowed.get(state["state"], set()): raise VisualSystemStateError(f"forbidden transition {state['state']} -> {target}")
    result=copy.deepcopy(state); result["history"].append({"from":state["state"],"to":target,"evidence":evidence}); result["state"]=target; return result


def record_host_pass(state: dict[str, Any], *, revision: bool = False, correction: bool = False) -> dict[str, Any]:
    result=copy.deepcopy(state); counters=result["counters"]
    if correction:
        if counters["current_pass_corrections"] >= 1: raise VisualSystemStateError("contract correction budget exhausted")
        counters["host_contract_correction_count"] += 1; counters["current_pass_corrections"] += 1
    elif revision:
        counters["host_revision_pass_count"] += 1; counters["current_pass_corrections"] = 0
    else:
        if counters["host_initial_pass_count"]: raise VisualSystemStateError("initial Host pass already used")
        counters["host_initial_pass_count"] = 1; counters["current_pass_corrections"] = 0
    counters["host_model_invocation_count"] += 1
    if counters["current_pass_corrections"] + 1 > result["budgets"]["max_host_invocations_per_pass"]: raise VisualSystemStateError("Host invocation budget exhausted")
    return result
