from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from content_plan_rules import approved_outline_from, route_event, validate_candidate_outline, validate_material_understanding, validate_outline_confirmation, validate_task_route
from content_plan_state import ContentPlanStateError, advance, initial_state
from deterministic_project_slide_content import build_projection, load_parent_hashes, write_projection
from schema_utils import ContractError, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Manage the deterministic P1 content-planning state")
    commands = result.add_subparsers(dest="action", required=True)
    init = commands.add_parser("init")
    init.add_argument("--task-id", required=True)
    init.add_argument("--deck-id", required=True)
    init.add_argument("--state", type=Path, required=True)
    route = commands.add_parser("route")
    route.add_argument("--state", type=Path, required=True)
    route.add_argument("--route", type=Path, required=True)
    materials = commands.add_parser("resolve-materials")
    materials.add_argument("--state", type=Path, required=True)
    materials.add_argument("--materials", type=Path, required=True)
    materials.add_argument("--resolution-sha256")
    candidate = commands.add_parser("submit-candidate")
    candidate.add_argument("--state", type=Path, required=True)
    candidate.add_argument("--candidate", type=Path, required=True)
    candidate.add_argument("--deck-request", type=Path, required=True)
    candidate.add_argument("--materials", type=Path, required=True)
    confirmation_request = commands.add_parser("request-confirmation")
    confirmation_request.add_argument("--state", type=Path, required=True)
    response = commands.add_parser("record-outline-response")
    response.add_argument("--state", type=Path, required=True)
    response.add_argument("--candidate", type=Path, required=True)
    response.add_argument("--confirmation", type=Path, required=True)
    response.add_argument("--approved-output", type=Path)
    response.add_argument("--approved-revision", type=int, default=1)
    response.add_argument("--parent-approved-sha256")
    projection = commands.add_parser("project-slide-content")
    projection.add_argument("--state", type=Path, required=True)
    projection.add_argument("--outline", type=Path, required=True)
    projection.add_argument("--output-dir", type=Path, required=True)
    projection.add_argument("--parent-content-dir", type=Path)
    projection.add_argument("--timestamp-utc")
    verify = commands.add_parser("verify")
    verify.add_argument("--state", type=Path, required=True)
    return result


def _save_state(path: Path, state: dict[str, Any]) -> dict[str, Any]:
    validate_schema("content_plan_state", state, SCHEMA_DIR)
    write_json(path, state)
    return state


def _route(state_path: Path, route_path: Path) -> dict[str, Any]:
    state = load_json(state_path)
    route = load_json(route_path)
    validate_task_route(route, SCHEMA_DIR)
    route_hash = canonical_sha256(route)
    if state["state"] == "received":
        state = advance(state, event="start_routing")
    elif state["state"] == "awaiting_route_clarification":
        clarification_hash = route.get("clarification_message_sha256")
        if not clarification_hash:
            raise ContentPlanStateError("a clarified route requires clarification_message_sha256")
        state = advance(state, event="clarification_received", user_evidence_sha256=clarification_hash)
    if state["state"] != "routing":
        raise ContentPlanStateError(f"route cannot be applied from {state['state']}")
    state = advance(state, event=route_event(route), artifact_kind="task_route", artifact_sha256=route_hash)
    return _save_state(state_path, state)


def _materials(state_path: Path, materials_path: Path, resolution_sha256: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    state = load_json(state_path)
    materials = load_json(materials_path)
    evaluation = validate_material_understanding(materials, SCHEMA_DIR)
    if state["state"] == "awaiting_material_resolution":
        if not resolution_sha256:
            raise ContentPlanStateError("material resolution requires user or replacement evidence")
        state = advance(state, event="material_resolution_received", user_evidence_sha256=resolution_sha256)
    if state["state"] != "material_intake":
        raise ContentPlanStateError(f"materials cannot be applied from {state['state']}")
    materials_hash = canonical_sha256(materials)
    event = "materials_ready" if evaluation["ready"] else "block_required_material"
    state = advance(state, event=event, artifact_kind="materials", artifact_sha256=materials_hash)
    return _save_state(state_path, state), evaluation


def _submit_candidate(state_path: Path, candidate_path: Path, deck_request_path: Path, materials_path: Path) -> dict[str, Any]:
    state = load_json(state_path)
    candidate = load_json(candidate_path)
    validate_candidate_outline(candidate, deck_request=load_json(deck_request_path), materials=load_json(materials_path), schema_dir=SCHEMA_DIR)
    candidate_hash = canonical_sha256(candidate)
    if state["state"] == "materials_ready":
        event = "initial_candidate_ready"
        user_hash = None
    elif state["state"] == "candidate_revision":
        event = "candidate_revised"
        user_hash = candidate.get("user_revision_request_sha256")
    else:
        raise ContentPlanStateError(f"candidate cannot be submitted from {state['state']}")
    state = advance(state, event=event, artifact_kind="candidate_outline", artifact_sha256=candidate_hash, user_evidence_sha256=user_hash)
    return _save_state(state_path, state)


def _request_confirmation(state_path: Path) -> dict[str, Any]:
    state = load_json(state_path)
    state = advance(state, event="request_outline_confirmation")
    return _save_state(state_path, state)


def _record_response(
    state_path: Path,
    candidate_path: Path,
    confirmation_path: Path,
    approved_output: Path | None,
    approved_revision: int,
    parent_approved_sha256: str | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    state = load_json(state_path)
    candidate = load_json(candidate_path)
    confirmation = load_json(confirmation_path)
    validate_outline_confirmation(candidate, confirmation, SCHEMA_DIR)
    if state["state"] != "awaiting_outline_confirmation":
        raise ContentPlanStateError(f"outline response cannot be recorded from {state['state']}")
    confirmation_hash = canonical_sha256(confirmation)
    status = confirmation["status"]
    if status == "changes_requested":
        state = advance(state, event="changes_requested", artifact_kind="confirmation", artifact_sha256=confirmation_hash, user_evidence_sha256=confirmation["user_message_sha256"])
        approved = None
    elif status == "rejected":
        state = advance(state, event="outline_rejected", artifact_kind="confirmation", artifact_sha256=confirmation_hash, user_evidence_sha256=confirmation["user_message_sha256"])
        approved = None
    else:
        if approved_output is None:
            raise ContentPlanStateError("confirmed outline requires --approved-output")
        approved = approved_outline_from(candidate, confirmation, revision=approved_revision, parent_sha256=parent_approved_sha256, approved_at_utc=confirmation["created_at_utc"])
        validate_schema("approved_outline", approved, SCHEMA_DIR)
        write_json(approved_output, approved)
        state = advance(state, event="outline_confirmed", artifact_kind="confirmation", artifact_sha256=confirmation_hash, user_evidence_sha256=confirmation["user_message_sha256"])
        state = advance(state, event="approved_outline_recorded", artifact_kind="approved_outline", artifact_sha256=canonical_sha256(approved))
    return _save_state(state_path, state), approved


def _project_content(state_path: Path, outline_path: Path, output_dir: Path, parent_content_dir: Path | None, timestamp_utc: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    state = load_json(state_path)
    approved = load_json(outline_path)
    validate_schema("approved_outline", approved, SCHEMA_DIR)
    approved_hash = canonical_sha256(approved)
    if state["state"] != "outline_approved" or state["current_artifacts"]["approved_outline_sha256"] != approved_hash:
        raise ContentPlanStateError("projection requires the current Approved Outline authority")
    if approved["revision"] > 1 and parent_content_dir is None:
        raise ContentPlanStateError("Approved Outline revision requires parent slide content")
    slides, manifest = build_projection(approved, frozen_at_utc=timestamp_utc, parent_hashes=load_parent_hashes(parent_content_dir) if parent_content_dir else None)
    projected_state = advance(state, event="start_projection")
    projected_state = advance(projected_state, event="projection_complete", artifact_kind="slide_content_manifest", artifact_sha256=canonical_sha256(manifest))
    projected_state = advance(projected_state, event="complete_p1")
    validate_schema("content_plan_state", projected_state, SCHEMA_DIR)
    write_projection(output_dir, slides, manifest)
    return _save_state(state_path, projected_state), manifest


def main() -> int:
    args = parser().parse_args()
    try:
        if args.action == "init":
            if args.state.exists():
                raise ContentPlanStateError(f"state already exists: {args.state}")
            state = _save_state(args.state.resolve(), initial_state(task_id=args.task_id, deck_id=args.deck_id))
            details: dict[str, Any] = {}
        elif args.action == "route":
            state = _route(args.state.resolve(), args.route.resolve())
            details = {}
        elif args.action == "resolve-materials":
            state, details = _materials(args.state.resolve(), args.materials.resolve(), args.resolution_sha256)
        elif args.action == "submit-candidate":
            state = _submit_candidate(args.state.resolve(), args.candidate.resolve(), args.deck_request.resolve(), args.materials.resolve())
            details = {}
        elif args.action == "request-confirmation":
            state = _request_confirmation(args.state.resolve())
            details = {}
        elif args.action == "record-outline-response":
            state, approved = _record_response(args.state.resolve(), args.candidate.resolve(), args.confirmation.resolve(), args.approved_output.resolve() if args.approved_output else None, args.approved_revision, args.parent_approved_sha256)
            details = {"approved_outline": str(args.approved_output.resolve()) if approved else None}
        elif args.action == "project-slide-content":
            state, manifest = _project_content(args.state.resolve(), args.outline.resolve(), args.output_dir.resolve(), args.parent_content_dir.resolve() if args.parent_content_dir else None, args.timestamp_utc)
            details = {"slides": len(manifest["slides"]), "manifest_sha256": canonical_sha256(manifest)}
        else:
            state = load_json(args.state.resolve())
            validate_schema("content_plan_state", state, SCHEMA_DIR)
            details = {"complete": state["state"] in {"p1_complete", "p1_bypassed"}}
        print(json.dumps({"status": "ok", "state": state["state"], "counters": state["counters"], **details}, ensure_ascii=False))
        return 0
    except (ContractError, ContentPlanStateError) as exc:
        errors = exc.errors if isinstance(exc, ContractError) else [{"code": "state_error", "message": str(exc)}]
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
