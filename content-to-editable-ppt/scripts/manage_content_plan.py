from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from content_plan_rules import route_event, validate_material_understanding, validate_task_route
from content_plan_state import ContentPlanStateError, advance, initial_state
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
        else:
            state, details = _materials(args.state.resolve(), args.materials.resolve(), args.resolution_sha256)
        print(json.dumps({"status": "ok", "state": state["state"], "counters": state["counters"], **details}, ensure_ascii=False))
        return 0
    except (ContractError, ContentPlanStateError) as exc:
        errors = exc.errors if isinstance(exc, ContractError) else [{"code": "state_error", "message": str(exc)}]
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
