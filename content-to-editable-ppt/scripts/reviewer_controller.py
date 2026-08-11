from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from agent_adapters import AgentAdapterError, AgentCallLedger
from asset_common import sha256_file
from iteration_common import append_transition, utc_now


TECHNICAL_FAILURE_CODES = {"reviewer_timeout", "reviewer_unavailable", "reviewer_technical_failure"}
MAX_REVIEWER_TECHNICAL_RETRIES = 2


class ReviewerControllerError(RuntimeError):
    pass


def route_reviewer_response(response: dict[str, Any]) -> str:
    recommendation = response.get("reviewer_recommendation")
    issues = response.get("issues", [])
    has_blocking_issue = any(item.get("severity") in {"major", "critical"} for item in issues)
    if recommendation == "pass" and not has_blocking_issue:
        return "pass"
    if recommendation in {"revise", "fail"} or has_blocking_issue:
        return "revision_required"
    raise ReviewerControllerError("Reviewer response has no classifiable recommendation")


def reviewer_failure_evidence(
    *,
    task_id: str,
    iteration: int,
    call_id: str,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    if not attempts:
        raise ReviewerControllerError("technical failure evidence requires at least one attempt")
    last = attempts[-1]
    return {
        "schema_version": "1.0",
        "task_id": task_id,
        "iteration": iteration,
        "call_id": call_id,
        "category": "technical_failure",
        "code": last["code"],
        "attempts": copy.deepcopy(attempts),
        "normalized_message": last["normalized_message"],
        "planner_calls": 0,
        "timestamp_utc": utc_now(),
    }


def run_reviewer_gate(
    adapter: Any,
    *,
    ledger: AgentCallLedger,
    task_id: str,
    iteration: int,
    call_id: str,
    structural_pass: bool,
    content_pass: bool,
    editability_pass: bool,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    for attempt in range(MAX_REVIEWER_TECHNICAL_RETRIES + 1):
        attempt_call_id = call_id if attempt == 0 else f"{call_id}-retry-{attempt}"
        try:
            response = adapter.invoke(role="reviewer", call_id=attempt_call_id, ledger=ledger)
            return {
                "status": route_reviewer_response(response),
                "attempt_count": attempt + 1,
                "technical_retry_count": attempt,
                "response": response,
                "technical_failure": None,
            }
        except AgentAdapterError as exc:
            if exc.code not in TECHNICAL_FAILURE_CODES:
                raise ReviewerControllerError(f"unclassified Reviewer error: {exc.code}") from exc
            failures.append({
                "attempt": attempt,
                "code": exc.code,
                "normalized_message": str(exc),
                "timeout_seconds": getattr(exc, "timeout_seconds", None),
                "exit_code": getattr(exc, "exit_code", None),
                "attempted_at_utc": utc_now(),
            })

    evidence = reviewer_failure_evidence(
        task_id=task_id,
        iteration=iteration,
        call_id=call_id,
        attempts=failures,
    )
    gates_pass = structural_pass and content_pass and editability_pass
    return {
        "status": "delivered_with_warnings" if gates_pass else "failed",
        "attempt_count": len(failures),
        "technical_retry_count": max(0, len(failures) - 1),
        "response": None,
        "technical_failure": evidence,
        "warning": "visual review incomplete" if gates_pass else None,
    }


def apply_technical_degradation(
    state: dict[str, Any],
    result: dict[str, Any],
    *,
    failure_path: Path,
    work_root: Path,
) -> dict[str, Any]:
    if result.get("status") != "delivered_with_warnings" or not result.get("technical_failure"):
        raise ReviewerControllerError("only an exhausted technical failure with passing gates may degrade delivery")
    if state.get("state") not in {"reviewing", "review_evaluating"}:
        raise ReviewerControllerError("Reviewer degradation requires an active Reviewer state")
    updated = append_transition(
        state,
        "delivered_with_warnings",
        "reviewer_technical_failure_exhausted",
        artifact=failure_path,
        work_root=work_root,
    )
    updated["review_degradation"] = {
        "reviewer_failure_sha256": sha256_file(failure_path),
        "warning": "visual review incomplete",
        "gates": {"structural": True, "content": True, "editability": True},
        "completed_at_utc": utc_now(),
    }
    return updated
