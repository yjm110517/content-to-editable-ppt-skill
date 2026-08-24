from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


class WireframeStateError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def initial_state(*, task_id: str, deck_id: str, approved_outline_sha256: str, slide_content_manifest_sha256: str, absolute_host_model_invocation_ceiling: int | None = None) -> dict[str, Any]:
    return {
        "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1",
        "artifact_type": "markdown_wireframe_state", "task_id": task_id, "deck_id": deck_id,
        "state": "inputs_validated", "active_pass_id": None, "current_revision": 0,
        "budgets": {"max_contract_corrections_per_pass": 2, "max_host_invocations_per_pass": 3,
                    "absolute_host_model_invocation_ceiling": absolute_host_model_invocation_ceiling},
        "counters": {"host_wireframe_initial_pass_count": 0, "host_wireframe_revision_pass_count": 0,
                     "host_wireframe_contract_correction_count": 0, "host_model_invocation_count": 0,
                     "current_pass_contract_corrections": 0, "current_pass_host_invocations": 0,
                     "automatic_wireframe_redesign_count": 0, "layout_planner_calls": 0,
                     "reviewer_calls": 0, "image_generation_calls": 0},
        "current_artifacts": {"approved_outline_sha256": approved_outline_sha256,
                              "slide_content_manifest_sha256": slide_content_manifest_sha256,
                              "candidate_sha256": None, "validation_report_sha256": None,
                              "wireframe_manifest_sha256": None, "wireframe_sha256": None,
                              "preview_sha256": None, "feedback_sha256": None},
        "changed_slide_ids": [], "history": [],
    }


def _record(state: dict[str, Any], *, event: str, target: str, artifact_sha256: str | None = None, user_evidence_sha256: str | None = None, host_model_invocation_id: str | None = None, affected_slide_ids: list[str] | None = None, timestamp_utc: str | None = None) -> dict[str, Any]:
    result = copy.deepcopy(state)
    result["history"].append({"from": state["state"], "to": target, "event": event,
                              "artifact_sha256": artifact_sha256, "user_evidence_sha256": user_evidence_sha256,
                              "host_model_invocation_id": host_model_invocation_id,
                              "affected_slide_ids": list(affected_slide_ids or []),
                              "timestamp_utc": timestamp_utc or utc_now()})
    result["state"] = target
    return result


def start_planning(state: dict[str, Any], *, pass_id: str, host_model_invocation_id: str, user_evidence_sha256: str | None = None) -> dict[str, Any]:
    if state["state"] not in {"inputs_validated", "revision_requested"}:
        raise WireframeStateError("planning requires inputs_validated or revision_requested")
    counters = copy.deepcopy(state["counters"])
    if state["state"] == "inputs_validated":
        if counters["host_wireframe_initial_pass_count"]:
            raise WireframeStateError("automatic initial regeneration is forbidden")
        counters["host_wireframe_initial_pass_count"] = 1
    else:
        if not user_evidence_sha256:
            raise WireframeStateError("revision planning requires user evidence")
        latest = next((item for item in reversed(state["history"]) if item["event"] in {"layout_changes_requested", "visual_storyboard_changes_requested"}), None)
        if latest is None or latest["user_evidence_sha256"] != user_evidence_sha256:
            raise WireframeStateError("revision does not bind latest layout feedback")
        counters["host_wireframe_revision_pass_count"] += 1
    if any(item.get("host_model_invocation_id") == host_model_invocation_id for item in state["history"]):
        raise WireframeStateError("host_model_invocation_id must be unique")
    ceiling = state["budgets"]["absolute_host_model_invocation_ceiling"]
    if ceiling is not None and counters["host_model_invocation_count"] >= ceiling:
        raise WireframeStateError("absolute Host invocation budget exhausted")
    counters["host_model_invocation_count"] += 1
    counters["current_pass_host_invocations"] = 1
    counters["current_pass_contract_corrections"] = 0
    result = _record(state, event="start_planning", target="wireframe_planning", user_evidence_sha256=user_evidence_sha256, host_model_invocation_id=host_model_invocation_id)
    result["active_pass_id"], result["counters"] = pass_id, counters
    return result


def submit_validation(state: dict[str, Any], *, candidate_sha256: str, report_sha256: str, status: str, host_model_invocation_id: str, pass_id: str, user_evidence_sha256: str | None = None) -> dict[str, Any]:
    if state["state"] in {"inputs_validated", "revision_requested"}:
        state = start_planning(state, pass_id=pass_id, host_model_invocation_id=host_model_invocation_id, user_evidence_sha256=user_evidence_sha256)
    elif state["state"] != "validating_candidate":
        if state["state"] != "wireframe_planning":
            raise WireframeStateError("candidate submission is invalid from current state")
    target = {"pass": "candidate_ready", "correctable": "contract_correction_required", "blocking": "wireframe_failed"}[status]
    result = _record(state, event="candidate_validated", target=target, artifact_sha256=report_sha256)
    result["current_artifacts"]["candidate_sha256"] = candidate_sha256
    result["current_artifacts"]["validation_report_sha256"] = report_sha256
    return result


def consume_correction(state: dict[str, Any], *, host_model_invocation_id: str) -> dict[str, Any]:
    if state["state"] != "contract_correction_required":
        raise WireframeStateError("correction requires contract_correction_required")
    counters = copy.deepcopy(state["counters"])
    if counters["current_pass_contract_corrections"] >= 2 or counters["current_pass_host_invocations"] >= 3:
        raise WireframeStateError("Contract Correction budget exhausted")
    ceiling = state["budgets"]["absolute_host_model_invocation_ceiling"]
    if ceiling is not None and counters["host_model_invocation_count"] >= ceiling:
        raise WireframeStateError("absolute Host invocation budget exhausted")
    if any(item.get("host_model_invocation_id") == host_model_invocation_id for item in state["history"]):
        raise WireframeStateError("host_model_invocation_id must be unique")
    counters["current_pass_contract_corrections"] += 1
    counters["current_pass_host_invocations"] += 1
    counters["host_wireframe_contract_correction_count"] += 1
    counters["host_model_invocation_count"] += 1
    result = _record(state, event="contract_correction_applied", target="validating_candidate", host_model_invocation_id=host_model_invocation_id)
    result["counters"] = counters
    return result


def mark_bound(state: dict[str, Any], *, revision: int, manifest_sha256: str, wireframe_sha256: str) -> dict[str, Any]:
    if state["state"] != "candidate_ready":
        raise WireframeStateError("binding requires candidate_ready")
    if revision != state["current_revision"] + 1:
        raise WireframeStateError("revision must increment exactly once")
    result = _record(state, event="markdown_bound", target="ready_for_preview", artifact_sha256=manifest_sha256)
    result["current_revision"] = revision
    result["current_artifacts"]["wireframe_manifest_sha256"] = manifest_sha256
    result["current_artifacts"]["wireframe_sha256"] = wireframe_sha256
    return result


def record_preview(state: dict[str, Any], *, preview_sha256: str, mode: str, user_message_sha256: str) -> dict[str, Any]:
    if state["state"] != "ready_for_preview":
        raise WireframeStateError("preview requires ready_for_preview")
    target = "p2_complete" if mode == "skipped" else "awaiting_wireframe_feedback"
    result = _record(state, event="preview_skipped" if mode == "skipped" else "preview_presented", target=target, artifact_sha256=preview_sha256, user_evidence_sha256=user_message_sha256)
    result["current_artifacts"]["preview_sha256"] = preview_sha256
    return result


def record_feedback(state: dict[str, Any], *, feedback_sha256: str, decision: str, scope: str, affected_slide_ids: list[str], user_message_sha256: str) -> dict[str, Any]:
    if state["state"] != "awaiting_wireframe_feedback":
        raise WireframeStateError("feedback requires awaiting_wireframe_feedback")
    if decision in {"accepted", "continue"}:
        target, event = "p2_complete", "wireframe_accepted"
    elif scope in {"layout", "visual_storyboard"}:
        target, event = "revision_requested", "visual_storyboard_changes_requested" if scope == "visual_storyboard" else "layout_changes_requested"
    else:
        target, event = "p1_revision_required", "content_changes_requested"
    result = _record(state, event=event, target=target, artifact_sha256=feedback_sha256, user_evidence_sha256=user_message_sha256, affected_slide_ids=affected_slide_ids)
    result["current_artifacts"]["feedback_sha256"] = feedback_sha256
    result["changed_slide_ids"] = list(affected_slide_ids) if target in {"revision_requested", "p1_revision_required"} else []
    return result


def request_visual_revision(state: dict[str, Any], *, feedback_sha256: str, affected_slide_ids: list[str], user_message_sha256: str) -> dict[str, Any]:
    if state["state"] != "p2_complete":
        raise WireframeStateError("visual revision requires p2_complete")
    if not affected_slide_ids:
        raise WireframeStateError("visual revision requires affected slides")
    result = _record(
        state,
        event="visual_storyboard_changes_requested",
        target="revision_requested",
        artifact_sha256=feedback_sha256,
        user_evidence_sha256=user_message_sha256,
        affected_slide_ids=affected_slide_ids,
    )
    result["current_artifacts"]["feedback_sha256"] = feedback_sha256
    result["changed_slide_ids"] = list(affected_slide_ids)
    ceiling = result["budgets"]["absolute_host_model_invocation_ceiling"]
    if ceiling is not None:
        result["budgets"]["absolute_host_model_invocation_ceiling"] = max(ceiling, result["counters"]["host_model_invocation_count"]) + result["budgets"]["max_host_invocations_per_pass"]
    return result


def authorize_revision_budget(state: dict[str, Any], *, user_evidence_sha256: str) -> dict[str, Any]:
    if state["state"] != "revision_requested":
        raise WireframeStateError("revision budget authorization requires revision_requested")
    request = next((item for item in reversed(state["history"]) if item["event"] in {"visual_storyboard_changes_requested", "layout_changes_requested"}), None)
    if request is None or request["user_evidence_sha256"] != user_evidence_sha256:
        raise WireframeStateError("revision budget authorization does not bind current user request")
    if any(item["event"] == "revision_budget_authorized" and item["user_evidence_sha256"] == user_evidence_sha256 for item in state["history"]):
        raise WireframeStateError("revision budget is already authorized")
    ceiling = state["budgets"]["absolute_host_model_invocation_ceiling"]
    if ceiling is None:
        raise WireframeStateError("unbounded Host budget does not require authorization")
    if ceiling - state["counters"]["host_model_invocation_count"] >= state["budgets"]["max_host_invocations_per_pass"]:
        raise WireframeStateError("revision budget is already authorized")
    result = _record(state, event="revision_budget_authorized", target="revision_requested", user_evidence_sha256=user_evidence_sha256, affected_slide_ids=state["changed_slide_ids"])
    result["budgets"]["absolute_host_model_invocation_ceiling"] = max(ceiling, state["counters"]["host_model_invocation_count"]) + state["budgets"]["max_host_invocations_per_pass"]
    return result
