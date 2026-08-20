from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from schema_utils import ContractError, error, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"

STAGE_MAPPING = {
    "text_or_data": "p1",
    "deck_visual_system": "p3_2",
    "approved_preview_or_visual_authority": "p3_3",
    "page_reconstruction_editability_geometry": "p4",
    "environment_security_roundtrip_packaging": "p5",
}

CONSISTENCY_DIMENSIONS = {
    "typography": "typography_consistent",
    "palette": "palette_consistent",
    "background": "background_consistent",
    "card_language": "card_language_consistent",
    "density_spacing": "density_spacing_consistent",
    "visual_treatment": "visual_treatment_consistent",
    "navigation": "navigation_consistent",
    "section_hierarchy": "section_hierarchy_consistent",
    "deck_identity": "same_deck_identity",
    "systemic_anomaly": "same_deck_identity",
}


def _validate_production_scope(response: dict[str, Any]) -> list[dict[str, str]]:
    if response.get("schema_version") != "1.1":
        return []
    failures: list[dict[str, str]] = []
    issues = response.get("issues", [])
    issue_by_id = {item.get("issue_id"): item for item in issues}
    mandatory = response.get("mandatory_checks", {})
    for index, item in enumerate(issues):
        base = f"$.issues[{index}]"
        compared = set(item["cross_slide_basis"]["compared_slide_ids"])
        affected = set(item["slide_ids"])
        if not affected.issubset(compared):
            failures.append(error(base + ".cross_slide_basis.compared_slide_ids", "cross-slide evidence must include every affected slide", "contract_violation"))
        if item["severity"] == "suggestion":
            impact = item["delivery_impact"]
            if any(impact.values()):
                failures.append(error(base + ".delivery_impact", "a suggestion cannot require artifact change, represent systemic inconsistency, or block accessibility", "unsafe_suggestion"))
            if any(status is False for status in mandatory.values()):
                failures.append(error(base, "a suggestion is forbidden while any mandatory consistency check fails", "unsafe_suggestion"))

    failed_checks = {name for name, status in mandatory.items() if status is False}
    for check in failed_checks:
        matching = [item for item in issues if item["severity"] != "suggestion" and CONSISTENCY_DIMENSIONS.get(item["dimension"]) == check]
        if not matching:
            failures.append(error(f"$.mandatory_checks.{check}", "a failed mandatory check requires a matching non-suggestion cross-slide finding", "contract_violation"))

    blocking_ids = {item["issue_id"] for item in issues if item["severity"] in {"critical", "major"}}
    upstream = response.get("structured_upstream_revision") or []
    upstream_ids = {issue_id for entry in upstream for issue_id in entry.get("issue_ids", [])}
    unknown = upstream_ids - set(issue_by_id)
    if unknown:
        failures.append(error("$.structured_upstream_revision.issue_ids", f"upstream revision references unknown issues: {sorted(unknown)}", "unknown_reference"))
    if blocking_ids - upstream_ids:
        failures.append(error("$.structured_upstream_revision", "every Critical/Major finding requires an issue-bound upstream revision", "contract_violation"))
    if issues and all(item["severity"] == "suggestion" for item in issues) and upstream:
        failures.append(error("$.structured_upstream_revision", "suggestion-only reviews cannot request an upstream revision", "unsafe_suggestion"))
    return failures


def prepare_deck_review_evidence(
    *,
    deck_id: str,
    contact_sheets: dict[str, Any],
    visual_system_summary: dict[str, Any],
    qa_report: dict[str, Any],
    roundtrip_report: dict[str, Any],
    fidelity_inheritance: dict[str, Any],
    exception_review_hashes: list[str],
) -> dict[str, Any]:
    """Assemble the fixed one-pass Deck Consistency Review evidence bundle."""
    evidence = {
        "schema_version": "1.0",
        "artifact_type": "deck_consistency_review_evidence",
        "deck_id": deck_id,
        "contact_sheets": contact_sheets,
        "visual_system_summary": visual_system_summary,
        "final_qa_report": {"status": qa_report.get("status"), "blocking_issues": qa_report.get("blocking_issues"), "exception_pages": qa_report.get("exception_pages")},
        "roundtrip_report": {"status": roundtrip_report.get("status"), "relationship_safety": roundtrip_report.get("relationship_safety")},
        "p4_fidelity_inheritance": fidelity_inheritance,
        "exception_review_hashes": exception_review_hashes,
        "reviewer_contract": {
            "scope": "cross-slide and systemic consistency only",
            "must_not_reopen_p4_fidelity": True,
        },
    }
    return evidence


def _mapping(stage: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", stage.lower()).strip("_")
    if normalized in STAGE_MAPPING:
        return STAGE_MAPPING[normalized]
    raise ContractError([error("$.structured_upstream_revision", f"unknown responsible stage: {stage}", "unknown_responsible_stage")])


def compile_consistency_report(
    *,
    deck_id: str,
    evidence: dict[str, Any],
    reviewer_response: dict[str, Any],
    call_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile deck-consistency-report.json from a VALIDATED reviewer response.

    A trusted review requires a Call Record binding evidence/raw/finalized/role/prompt/schema hashes,
    a fresh context id, and technical retry history. Responses without a Call Record are
    deterministic fixtures and are flagged with does_not_satisfy_adr_040 = true.
    """
    validate_schema("deck_consistency_reviewer_response", reviewer_response, SCHEMA_DIR)
    failures: list[dict[str, str]] = []
    if reviewer_response.get("deck_id") != deck_id:
        failures.append(error("$.deck_id", "Reviewer response belongs to another deck", "authority_deck_mismatch"))
    issues = reviewer_response.get("issues", [])
    mandatory = reviewer_response.get("mandatory_checks", {})
    failed_checks = [name for name, status in mandatory.items() if status is False]
    recommendation = reviewer_response.get("reviewer_recommendation")
    if recommendation == "pass" and failed_checks:
        failures.append(error("$.reviewer_recommendation", "pass is forbidden while a consistency check fails", "contract_violation"))
    failures.extend(_validate_production_scope(reviewer_response))
    if failures:
        raise ContractError(failures)

    trusted = call_record is not None
    if trusted:
        required_bindings = ("evidence_sha256", "raw_response_sha256", "finalized_response_sha256", "role_config_sha256", "prompt_sha256", "response_schema_sha256", "resolved_model_identity_sha256", "transport_request_sha256", "context_id")
        missing = [field for field in required_bindings if not call_record.get(field)]
        if missing:
            raise ContractError([error("$.call_record", f"trusted call record is missing bindings: {missing}", "missing_call_record_bindings")])

    upstream = reviewer_response.get("structured_upstream_revision")
    upstream_entries = None
    if upstream:
        entries = []
        for index, item in enumerate(upstream):
            stage = _mapping(item["responsible_stage"])
            entries.append({
                "responsible_stage": stage,
                "issue_ids": item.get("issue_ids", []),
                "affected_slide_ids": item.get("affected_slide_ids", []),
                "reason_code": item.get("reason_code", ""),
                "required_revision_scope": item.get("required_revision_scope", ""),
            })
        upstream_entries = entries

    report = {
        "schema_version": "1.0",
        "artifact_type": "deck_consistency_report",
        "deck_id": deck_id,
        "reviewer_recommendation": recommendation,
        "issues": issues,
        "mandatory_checks": mandatory,
        "structured_upstream_revision": upstream_entries,
        "evidence": {
            "contact_sheets_sha256": [item["sha256"] for item in evidence.get("contact_sheets", {}).values() if isinstance(item, dict) and "sha256" in item],
            "exception_review_hashes": evidence.get("exception_review_hashes", []),
        },
        "call_record": call_record,
        "does_not_satisfy_adr_040": not trusted,
    }
    validate_schema("deck_consistency_report", report, SCHEMA_DIR)
    return report
