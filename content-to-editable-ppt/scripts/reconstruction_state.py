from __future__ import annotations

from copy import deepcopy
from typing import Any

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error


DECK_TRANSITIONS = {
    "p3_3_complete": {"reconstruction_preflight"},
    "reconstruction_preflight": {"asset_manifest_ready", "p4_failed"},
    "asset_manifest_ready": {"smoke_set_selected", "p4_failed"},
    "smoke_set_selected": {"smoke_reconstructing", "p4_failed"},
    "smoke_reconstructing": {"smoke_failed", "smoke_passed"},
    "smoke_passed": {"reconstructing_pages"},
    "reconstructing_pages": {"pages_reconstructed", "p4_failed"},
    "pages_reconstructed": {"building_candidate_deck"},
    "building_candidate_deck": {"rendering_candidate_deck", "p4_failed"},
    "rendering_candidate_deck": {"post_assembly_comparison", "p4_failed"},
    "post_assembly_comparison": {"p4_complete", "p4_failed"},
}

PAGE_TRANSITIONS = {
    "received": {"authority_validated", "failed"},
    "authority_validated": {"seed_ready", "failed"},
    "seed_ready": {"spec_compiled", "failed"},
    "spec_compiled": {"spec_validated", "failed"},
    "spec_validated": {"building", "failed"},
    "building": {"rendering", "failed"},
    "rendering": {"deterministic_qa", "failed"},
    "deterministic_qa": {"fidelity_comparison", "failed"},
    "fidelity_comparison": {"page_reconstructed", "targeted_patch_required", "failed"},
    "targeted_patch_required": {"patching", "failed"},
    "patching": {"spec_validated", "failed"},
}


def initial_deck_state(deck_id: str, approved_manifest_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0", "artifact_type": "reconstruction_deck_state", "deck_id": deck_id,
        "state": "p3_3_complete",
        "budgets": {"smoke_page_limit": 2, "targeted_patch_per_page": 2, "technical_retry_per_stage": 2, "reviewer_per_exception": 1},
        "counters": {"initial_planner_calls": 0, "targeted_patch_planner_calls": 0, "reviewer_calls": 0, "image_generation_calls": 0},
        "page_states": [],
        "current_artifacts": {"approved_design_preview_manifest_sha256": approved_manifest_sha256},
        "history": [],
    }


def initial_page_state(deck_id: str, slide_id: str) -> dict[str, Any]:
    return {"schema_version": "1.0", "artifact_type": "reconstruction_page_state", "deck_id": deck_id, "slide_id": slide_id, "state": "received", "iteration": 1, "technical_retry_count": 0, "targeted_patch_count": 0, "planner_calls": 0, "reviewer_calls": 0, "current_artifacts": {}, "history": []}


def transition(document: dict[str, Any], next_state: str, *, artifact_updates: dict[str, Any] | None = None) -> dict[str, Any]:
    kind = document.get("artifact_type")
    allowed = DECK_TRANSITIONS if kind == "reconstruction_deck_state" else PAGE_TRANSITIONS if kind == "reconstruction_page_state" else None
    if allowed is None or next_state not in allowed.get(document.get("state"), set()):
        raise ContractError([error("$.state", f"invalid transition: {document.get('state')} -> {next_state}", "invalid_state_transition")])
    result = deepcopy(document)
    result["history"].append({"from": document["state"], "to": next_state, "previous_sha256": canonical_sha256(document)})
    result["state"] = next_state
    if artifact_updates:
        result["current_artifacts"].update(artifact_updates)
    return result
