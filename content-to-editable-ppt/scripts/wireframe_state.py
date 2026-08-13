from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


class WireframeStateError(ValueError):
    pass


TRANSITIONS = {
    ("received", "start_input_validation"): "validating_inputs",
    ("validating_inputs", "bypass_image_route"): "p2_bypassed",
    ("validating_inputs", "inputs_accepted"): "inputs_validated",
    ("inputs_validated", "start_initial_planning"): "wireframe_planning",
    ("wireframe_planning", "candidate_specs_ready"): "candidate_specs_ready",
    ("candidate_specs_ready", "start_spec_validation"): "validating_specs",
    ("validating_specs", "contract_correction_required"): "contract_correction_required",
    ("contract_correction_required", "start_contract_correction"): "applying_contract_correction",
    ("applying_contract_correction", "contract_correction_applied"): "candidate_specs_ready",
    ("validating_specs", "specs_accepted"): "specs_accepted",
    ("specs_accepted", "start_rendering"): "rendering",
    ("rendering", "rendering_complete"): "rendered",
    ("rendered", "preview_recorded"): "preview_recorded",
    ("preview_recorded", "complete_without_feedback"): "p2_complete",
    ("preview_recorded", "wait_for_feedback"): "awaiting_wireframe_feedback",
    ("awaiting_wireframe_feedback", "feedback_continue"): "p2_complete",
    ("awaiting_wireframe_feedback", "feedback_changes_requested"): "revision_requested",
    ("awaiting_wireframe_feedback", "feedback_content_changes_requested"): "p1_revision_required",
    ("revision_requested", "start_revision_planning"): "wireframe_planning",
}


TERMINAL = {"p2_bypassed", "p1_revision_required", "wireframe_failed"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def initial_state(*, task_id: str, deck_id: str, absolute_host_model_invocation_ceiling: int | None = None) -> dict[str, Any]:
    if absolute_host_model_invocation_ceiling is not None and absolute_host_model_invocation_ceiling < 1:
        raise WireframeStateError("absolute Host invocation ceiling must be positive")
    return {
        "schema_version": "1.1",
        "canonicalization_version": "p1-rfc8785-nfc-1",
        "task_id": task_id,
        "deck_id": deck_id,
        "state": "received",
        "active_pass_id": None,
        "budgets": {
            "max_contract_corrections_per_pass": 2,
            "max_host_invocations_per_pass": 3,
            "absolute_host_model_invocation_ceiling": absolute_host_model_invocation_ceiling,
        },
        "counters": {
            "host_wireframe_initial_pass_count": 0,
            "host_wireframe_revision_pass_count": 0,
            "host_wireframe_contract_correction_count": 0,
            "host_model_invocation_count": 0,
            "current_pass_contract_corrections": 0,
            "current_pass_host_invocations": 0,
            "automatic_wireframe_redesign_count": 0,
            "layout_planner_calls": 0,
            "reviewer_calls": 0,
            "image_generation_calls": 0,
        },
        "current_artifacts": {
            "layout_requirements_sha256": None,
            "approved_outline_sha256": None,
            "slide_content_manifest_sha256": None,
            "candidate_manifest_sha256": None,
            "wireframe_manifest_sha256": None,
            "preview_sha256": None,
            "feedback_sha256": None,
        },
        "changed_slide_ids": [],
        "page_results": [],
        "history": [],
    }


def _consume_host_invocation(updated: dict[str, Any], invocation_id: str | None, *, correction: bool) -> None:
    if not invocation_id:
        raise WireframeStateError("Host planning and correction events require host_model_invocation_id")
    counters = updated["counters"]
    if any(item.get("host_model_invocation_id") == invocation_id for item in updated["history"]):
        raise WireframeStateError("host_model_invocation_id must be unique")
    if counters["current_pass_host_invocations"] >= updated["budgets"]["max_host_invocations_per_pass"]:
        raise WireframeStateError("current Host pass invocation budget is exhausted")
    ceiling = updated["budgets"]["absolute_host_model_invocation_ceiling"]
    if ceiling is not None and counters["host_model_invocation_count"] >= ceiling:
        raise WireframeStateError("absolute Host model invocation budget is exhausted")
    counters["current_pass_host_invocations"] += 1
    counters["host_model_invocation_count"] += 1
    if correction:
        if counters["current_pass_contract_corrections"] >= updated["budgets"]["max_contract_corrections_per_pass"]:
            raise WireframeStateError("Contract Correction budget is exhausted")
        counters["current_pass_contract_corrections"] += 1
        counters["host_wireframe_contract_correction_count"] += 1


def advance(
    state: dict[str, Any],
    *,
    event: str,
    artifact_kind: str | None = None,
    artifact_sha256: str | None = None,
    user_evidence_sha256: str | None = None,
    affected_slide_ids: list[str] | None = None,
    host_model_invocation_id: str | None = None,
    pass_id: str | None = None,
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    current = state.get("state")
    if event == "fail":
        if current in TERMINAL:
            raise WireframeStateError(f"cannot fail terminal state {current}")
        target = "wireframe_failed"
    else:
        target = TRANSITIONS.get((current, event))
        if target is None:
            raise WireframeStateError(f"event {event} is invalid from {current}")
    updated = copy.deepcopy(state)
    counters = updated["counters"]
    if event in {"start_revision_planning", "feedback_changes_requested", "feedback_content_changes_requested", "feedback_continue"} and not user_evidence_sha256:
        raise WireframeStateError(f"event {event} requires user evidence")
    if event == "start_initial_planning":
        if counters["host_wireframe_initial_pass_count"] != 0:
            raise WireframeStateError("automatic Host Wireframe regeneration is forbidden")
        if not pass_id:
            raise WireframeStateError("initial planning requires pass_id")
        updated["active_pass_id"] = pass_id
        counters["host_wireframe_initial_pass_count"] = 1
        counters["current_pass_contract_corrections"] = 0
        counters["current_pass_host_invocations"] = 0
        _consume_host_invocation(updated, host_model_invocation_id, correction=False)
    elif event == "start_revision_planning":
        if not pass_id:
            raise WireframeStateError("revision planning requires pass_id")
        request = next((item for item in reversed(updated["history"]) if item["event"] == "feedback_changes_requested"), None)
        if request is None or request["user_evidence_sha256"] != user_evidence_sha256:
            raise WireframeStateError("revision does not bind the latest user feedback")
        updated["active_pass_id"] = pass_id
        counters["host_wireframe_revision_pass_count"] += 1
        counters["current_pass_contract_corrections"] = 0
        counters["current_pass_host_invocations"] = 0
        _consume_host_invocation(updated, host_model_invocation_id, correction=False)
    elif event == "start_contract_correction":
        _consume_host_invocation(updated, host_model_invocation_id, correction=True)
    if event in {"feedback_changes_requested", "feedback_content_changes_requested"}:
        if not affected_slide_ids:
            raise WireframeStateError(f"event {event} requires affected slides")
        updated["changed_slide_ids"] = list(affected_slide_ids)
    elif event == "feedback_continue":
        updated["changed_slide_ids"] = []
    if counters["automatic_wireframe_redesign_count"] or counters["layout_planner_calls"] or counters["reviewer_calls"] or counters["image_generation_calls"]:
        raise WireframeStateError("P2 forbids automatic redesign and Specialist Agent calls")
    if artifact_kind:
        field = f"{artifact_kind}_sha256"
        if field not in updated["current_artifacts"] or not artifact_sha256:
            raise WireframeStateError("invalid authority artifact update")
        updated["current_artifacts"][field] = artifact_sha256
    updated["history"].append({
        "from": current,
        "to": target,
        "event": event,
        "artifact_kind": artifact_kind,
        "artifact_sha256": artifact_sha256,
        "user_evidence_sha256": user_evidence_sha256,
        "affected_slide_ids": list(affected_slide_ids or []),
        "host_model_invocation_id": host_model_invocation_id,
        "timestamp_utc": timestamp_utc or utc_now(),
    })
    updated["state"] = target
    return updated
