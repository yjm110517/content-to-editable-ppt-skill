from __future__ import annotations

from typing import Any

from schema_utils import ContractError, error


def evaluate_delivery_policy(
    *,
    severity_counts: dict[str, int],
    review_incomplete: int,
    unexpected_reviewer_calls: int,
) -> dict[str, Any]:
    """Deterministic delivery policy.

    Critical / Major / Review Incomplete / Unexpected Reviewer Calls -> not deliverable.
    Minor only -> awaiting_warning_acceptance.
    No issues or suggestions only -> pass.
    """
    critical = severity_counts.get("critical", 0)
    major = severity_counts.get("major", 0)
    minor = severity_counts.get("minor", 0)
    if critical < 0 or major < 0 or minor < 0 or review_incomplete < 0 or unexpected_reviewer_calls < 0:
        raise ContractError([error("$.severity_counts", "counts must be non-negative", "invalid_policy_input")])
    if critical or major or review_incomplete or unexpected_reviewer_calls:
        status = "not_deliverable"
        decision_state = "upstream_revision_required"
    elif minor:
        status = "awaiting_warning_acceptance"
        decision_state = "awaiting_warning_acceptance"
    else:
        status = "pass"
        decision_state = "delivery_approved"
    return {
        "policy_status": status,
        "decision_state": decision_state,
        "severity_counts": {"critical": critical, "major": major, "minor": minor, "suggestion": severity_counts.get("suggestion", 0)},
        "review_incomplete": review_incomplete,
        "unexpected_reviewer_calls": unexpected_reviewer_calls,
    }
