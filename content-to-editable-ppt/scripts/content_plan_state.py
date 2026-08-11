from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any


class ContentPlanStateError(ValueError):
    pass


TRANSITIONS = {
    ("received", "start_routing"): "routing",
    ("routing", "request_route_clarification"): "awaiting_route_clarification",
    ("awaiting_route_clarification", "clarification_received"): "routing",
    ("routing", "route_image_to_ppt"): "p1_bypassed",
    ("routing", "route_content_to_ppt"): "material_intake",
    ("material_intake", "block_required_material"): "awaiting_material_resolution",
    ("awaiting_material_resolution", "material_resolution_received"): "material_intake",
    ("material_intake", "materials_ready"): "materials_ready",
    ("materials_ready", "initial_candidate_ready"): "candidate_ready",
    ("candidate_ready", "request_outline_confirmation"): "awaiting_outline_confirmation",
    ("awaiting_outline_confirmation", "changes_requested"): "candidate_revision",
    ("candidate_revision", "candidate_revised"): "candidate_ready",
    ("awaiting_outline_confirmation", "outline_confirmed"): "outline_approved",
    ("awaiting_outline_confirmation", "outline_rejected"): "outline_rejected",
    ("outline_approved", "approved_outline_recorded"): "outline_approved",
    ("outline_approved", "start_projection"): "projecting_slide_content",
    ("projecting_slide_content", "projection_complete"): "slide_content_frozen",
    ("slide_content_frozen", "complete_p1"): "p1_complete",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def initial_state(*, task_id: str, deck_id: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "canonicalization_version": "p1-rfc8785-nfc-1",
        "task_id": task_id,
        "deck_id": deck_id,
        "state": "received",
        "counters": {
            "host_planning_pass_count": 0,
            "host_revision_pass_count": 0,
            "automatic_regeneration_count": 0,
            "planner_calls": 0,
            "reviewer_calls": 0,
        },
        "current_artifacts": {
            "task_route_sha256": None,
            "materials_sha256": None,
            "candidate_outline_sha256": None,
            "confirmation_sha256": None,
            "approved_outline_sha256": None,
            "slide_content_manifest_sha256": None,
        },
        "history": [],
    }


def advance(
    state: dict[str, Any],
    *,
    event: str,
    artifact_kind: str | None = None,
    artifact_sha256: str | None = None,
    user_evidence_sha256: str | None = None,
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    current = state.get("state")
    target = TRANSITIONS.get((current, event))
    if target is None:
        raise ContentPlanStateError(f"event {event} is invalid from {current}")
    if event in {"changes_requested", "candidate_revised", "outline_confirmed", "outline_rejected"} and not user_evidence_sha256:
        raise ContentPlanStateError(f"event {event} requires user evidence")
    if event == "candidate_revised":
        requested = next((item["user_evidence_sha256"] for item in reversed(state["history"]) if item["event"] == "changes_requested"), None)
        if requested != user_evidence_sha256:
            raise ContentPlanStateError("candidate revision does not bind the latest user change request")
    updated = copy.deepcopy(state)
    counters = updated["counters"]
    if event == "initial_candidate_ready":
        if counters["host_planning_pass_count"] != 0:
            raise ContentPlanStateError("automatic Host regeneration is forbidden")
        counters["host_planning_pass_count"] = 1
    elif event == "candidate_revised":
        counters["host_revision_pass_count"] += 1
    if counters["automatic_regeneration_count"] != 0 or counters["planner_calls"] != 0 or counters["reviewer_calls"] != 0:
        raise ContentPlanStateError("P1 forbids automatic regeneration and Specialist Agent calls")
    if artifact_kind:
        field = f"{artifact_kind}_sha256"
        if field not in updated["current_artifacts"]:
            raise ContentPlanStateError(f"unknown authority artifact kind: {artifact_kind}")
        if not artifact_sha256:
            raise ContentPlanStateError("artifact updates require a SHA-256")
        updated["current_artifacts"][field] = artifact_sha256
    updated["history"].append({
        "from": current,
        "to": target,
        "event": event,
        "artifact_kind": artifact_kind,
        "artifact_sha256": artifact_sha256,
        "user_evidence_sha256": user_evidence_sha256,
        "timestamp_utc": timestamp_utc or utc_now(),
    })
    updated["state"] = target
    return updated
