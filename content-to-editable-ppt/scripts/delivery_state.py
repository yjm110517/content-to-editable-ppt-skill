from __future__ import annotations

from copy import deepcopy
from typing import Any

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error


DELIVERY_TRANSITIONS = {
    "p4_complete": {"p5_preflight"},
    "p5_preflight": {"final_integrity_check", "p4_revalidation_required", "p5_failed"},
    "final_integrity_check": {"deterministic_deck_qa", "p4_revalidation_required", "p5_failed"},
    "deterministic_deck_qa": {"roundtrip_check", "p5_failed"},
    "roundtrip_check": {"exception_review_routing", "p5_failed"},
    "exception_review_routing": {"deck_consistency_review_ready", "p5_failed"},
    "deck_consistency_review_ready": {"live_review_pending", "deck_consistency_review_complete", "p5_failed"},
    "live_review_pending": {"deck_consistency_review_complete", "p5_failed"},
    "deck_consistency_review_complete": {"evaluating_delivery_policy", "p5_failed"},
    "evaluating_delivery_policy": {"upstream_revision_required", "awaiting_warning_acceptance", "delivery_approved", "p5_failed"},
    "upstream_revision_required": {"p4_revalidation_required", "p5_failed"},
    "awaiting_warning_acceptance": {"delivery_approved", "p5_failed"},
    "delivery_approved": {"packaging", "p5_failed"},
    "packaging": {"delivered", "p5_failed"},
    "delivered": set(),
    "p4_revalidation_required": set(),
    "p5_failed": set(),
}


def initial_delivery_state(deck_id: str, p4_state_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "artifact_type": "deck_delivery_state",
        "deck_id": deck_id,
        "state": "p4_complete",
        "budgets": {
            "exception_batch_size": 4,
            "exception_batch_calls": 2,
            "reviewer_technical_retries": 2,
            "deck_consistency_passes": 1,
        },
        "counters": {
            "exception_reviewer_calls": 0,
            "deck_reviewer_calls": 0,
            "unexpected_reviewer_calls": 0,
        },
        "current_artifacts": {"p4_state_sha256": p4_state_sha256},
        "warning_acceptance": None,
        "history": [],
    }


def transition(document: dict[str, Any], next_state: str, *, artifact_updates: dict[str, Any] | None = None) -> dict[str, Any]:
    if document.get("artifact_type") != "deck_delivery_state":
        raise ContractError([error("$.artifact_type", "document is not a deck delivery state", "invalid_artifact_type")])
    allowed = DELIVERY_TRANSITIONS.get(document.get("state"), set())
    if next_state not in allowed:
        raise ContractError([error("$.state", f"invalid transition: {document.get('state')} -> {next_state}", "invalid_state_transition")])
    result = deepcopy(document)
    result["history"].append({"from": document["state"], "to": next_state, "previous_sha256": canonical_sha256(document)})
    result["state"] = next_state
    if artifact_updates:
        result["current_artifacts"].update(artifact_updates)
    return result
