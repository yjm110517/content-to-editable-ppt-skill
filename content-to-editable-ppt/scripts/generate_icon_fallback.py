from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from resolve_icon_asset import (
    SCHEMA_DIR,
    find_visual_context,
    json_bytes,
    validate_direction,
    validate_p2,
    validate_selection_decision,
    write_once,
)
from schema_utils import ContractError, error, load_json, validate_schema


def _authority(args: argparse.Namespace) -> tuple[dict[str, Any], str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest, manifest_sha = validate_p2(args.p2_manifest.resolve(), args.wireframe_root.resolve())
    slide, visual = find_visual_context(manifest, args.visual_ref)
    direction = validate_direction(args.visual_direction.resolve(), manifest, manifest_sha)
    evidence = load_json(args.search_evidence.resolve())
    validate_schema("icon_search_evidence", evidence, SCHEMA_DIR)
    if evidence["visual_ref"] != args.visual_ref or evidence["p2_manifest_sha256"] != manifest_sha:
        raise ContractError([error("$.search_evidence", "Search Evidence does not bind current P2 Authority", "authority_hash_mismatch")])
    if evidence["status"] != "host_selection_required":
        raise ContractError([error("$.search_evidence.status", "Host decision is only valid for host-selection evidence", "invalid_selection")])
    return manifest, manifest_sha, slide, visual, direction, evidence


def record_decision(args: argparse.Namespace) -> dict[str, Any]:
    manifest, manifest_sha, slide, _visual, direction, evidence = _authority(args)
    selected_icon = args.selected_icon
    if args.decision == "select_tabler":
        candidates = [item for item in evidence["top_k"] if item["name"] == selected_icon]
        if len(candidates) != 1:
            raise ContractError([error("$.selected_icon", "Host selection must be a unique current Top-K candidate", "selection_not_in_top_k")])
        reason = "accurate_top_k_match"
    else:
        if selected_icon is not None:
            raise ContractError([error("$.selected_icon", "Raster handoff cannot select an icon", "invalid_selection")])
        reason = "no_accurate_tabler_match"
    record = {
        "schema_version": "1.0",
        "artifact_type": "icon_selection_decision",
        "deck_id": manifest["deck_id"],
        "slide_id": slide["slide_id"],
        "visual_ref": args.visual_ref,
        "p2_manifest_sha256": manifest_sha,
        "visual_direction_sha256": canonical_sha256(direction),
        "search_evidence_sha256": canonical_sha256(evidence),
        "decision": args.decision,
        "selected_icon": selected_icon,
        "reason": reason,
        "created_at_utc": args.created_at_utc,
    }
    validate_schema("icon_selection_decision", record, SCHEMA_DIR)
    write_once(args.output.resolve(), json_bytes(record))
    return {"selection_decision": str(args.output.resolve()), "selection_decision_sha256": canonical_sha256(record)}


def create_handoff(args: argparse.Namespace) -> dict[str, Any]:
    manifest, manifest_sha, slide, visual, direction, evidence = _authority(args)
    decision = validate_selection_decision(
        args.selection_decision.resolve(), manifest=manifest, manifest_sha=manifest_sha,
        direction=direction, evidence=evidence, expected_decision="raster_handoff", selected_icon=None,
    )
    record = {
        "schema_version": "1.0",
        "artifact_type": "raster_handoff_pending",
        "deck_id": manifest["deck_id"],
        "slide_id": slide["slide_id"],
        "visual_ref": args.visual_ref,
        "semantic": visual["semantic"],
        "semantic_source_refs": visual["semantic_source_refs"],
        "p2_manifest_sha256": manifest_sha,
        "visual_direction_sha256": canonical_sha256(direction),
        "search_evidence_sha256": canonical_sha256(evidence),
        "selection_decision_sha256": canonical_sha256(decision),
        "reason": "no_accurate_tabler_match",
        "status": "raster_handoff_pending",
        "created_at_utc": args.created_at_utc,
    }
    validate_schema("raster_handoff_pending", record, SCHEMA_DIR)
    write_once(args.output.resolve(), json_bytes(record))
    return {"handoff_record": str(args.output.resolve()), "status": record["status"]}


def common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--p2-manifest", type=Path, required=True)
    parser.add_argument("--wireframe-root", type=Path, required=True)
    parser.add_argument("--visual-direction", type=Path, required=True)
    parser.add_argument("--search-evidence", type=Path, required=True)
    parser.add_argument("--visual-ref", required=True)
    parser.add_argument("--created-at-utc", required=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Record P3.1 Host selection or Raster Handoff Pending")
    sub = result.add_subparsers(dest="action", required=True)
    decision = sub.add_parser("record-decision")
    common(decision)
    decision.add_argument("--decision", choices=["select_tabler", "raster_handoff"], required=True)
    decision.add_argument("--selected-icon")
    decision.add_argument("--output", type=Path, required=True)
    handoff = sub.add_parser("create-handoff")
    common(handoff)
    handoff.add_argument("--selection-decision", type=Path, required=True)
    handoff.add_argument("--output", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        outputs = {"record-decision": record_decision, "create-handoff": create_handoff}[args.action](args)
        print(json.dumps({"status": "ok", "outputs": outputs}, ensure_ascii=False))
        return 0
    except (ContractError, OSError, ValueError) as exc:
        errors = exc.errors if isinstance(exc, ContractError) else [{"path": "$", "code": "fallback_error", "message": str(exc)}]
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
