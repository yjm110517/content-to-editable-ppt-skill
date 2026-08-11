from __future__ import annotations

from typing import Any


EVIDENCE_KEYS = (
    "content_regression",
    "editability_regression",
    "topology_regression",
    "structural_qa_regression",
    "artifact_regression",
    "related_runtime_input_changed",
)


def attribute_issue(
    *,
    case_id: str,
    reviewer_severity: str,
    deterministic_evidence: dict[str, bool],
    pre_existing_visual_issue: bool,
) -> dict[str, Any]:
    missing = [key for key in EVIDENCE_KEYS if key not in deterministic_evidence]
    if missing:
        raise ValueError(f"missing deterministic attribution evidence: {', '.join(missing)}")
    regressions = [key for key in EVIDENCE_KEYS if deterministic_evidence[key]]
    if regressions:
        classification = "runtime_regression"
        reasons = [f"deterministic:{key}" for key in regressions]
    elif pre_existing_visual_issue:
        classification = "pre_existing_visual_issue"
        reasons = ["matched_frozen_baseline_issue"]
    else:
        classification = "agent_variance_candidate"
        reasons = ["reviewer_severity_has_no_deterministic_regression_evidence"]
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "reviewer_severity": reviewer_severity,
        "classification": classification,
        "deterministic_evidence": {key: bool(deterministic_evidence[key]) for key in EVIDENCE_KEYS},
        "reasons": reasons,
    }
