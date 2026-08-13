from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from render_wireframe import audit_svg, render_document
from schema_utils import ContractError, error, is_safe_relative_path, load_json, validate_schema
from wireframe_rules import SCHEMA_DIR, apply_correction, build_manifest, candidate_manifest_digest, load_authority_bundle
from wireframe_state import WireframeStateError, advance, initial_state


def write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ContractError([error(str(path), "refusing to overwrite an existing artifact", "overwrite_forbidden")])
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def replace_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_specs(directory: Path) -> list[dict[str, Any]]:
    return [load_json(path) for path in sorted(directory.glob("*.json"))]


def _validate_state(state: dict[str, Any]) -> None:
    validate_schema("wireframe_state", state, SCHEMA_DIR)


def _projection_bundle(state: dict[str, Any], slide_content_dir: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    projection_path = slide_content_dir / "projection-manifest.json"
    if not projection_path.is_file():
        raise ContractError([error(str(projection_path), "Projection Manifest is missing", "missing_authority")])
    projection = load_json(projection_path)
    frozen = state["current_artifacts"]["slide_content_manifest_sha256"]
    if frozen is None or canonical_sha256(projection) != frozen:
        raise ContractError([error(str(projection_path), "Projection Manifest does not match frozen P2 Authority", "authority_hash_mismatch")])
    if projection.get("deck_id") != state["deck_id"] or not isinstance(projection.get("slides"), list):
        raise ContractError([error(str(projection_path), "Projection Manifest identity is invalid", "authority_identity_mismatch")])
    paths: dict[str, Path] = {}
    for index, item in enumerate(projection["slides"]):
        relative = item.get("path")
        if not isinstance(relative, str) or not is_safe_relative_path(relative):
            raise ContractError([error(f"$.slides[{index}].path", "unsafe Approved Slide Content path", "unsafe_path")])
        path = (slide_content_dir / relative).resolve()
        try:
            path.relative_to(slide_content_dir.resolve())
        except ValueError as exc:
            raise ContractError([error(f"$.slides[{index}].path", "Approved Slide Content escapes its directory", "unsafe_path")]) from exc
        document = load_json(path)
        validate_schema("approved_slide_content", document, SCHEMA_DIR)
        if document["deck_id"] != state["deck_id"] or document["slide_id"] != item.get("slide_id") or canonical_sha256(document) != item.get("sha256"):
            raise ContractError([error(f"$.slides[{index}]", "Approved Slide Content does not match Projection Manifest", "authority_hash_mismatch")])
        if item["slide_id"] in paths:
            raise ContractError([error(f"$.slides[{index}].slide_id", "duplicate Slide ID", "authority_identity_mismatch")])
        paths[item["slide_id"]] = path
    return projection, paths


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Manage deterministic P2 Wireframe state and artifacts")
    commands = result.add_subparsers(dest="action", required=True)
    init = commands.add_parser("init")
    init.add_argument("--task-id", required=True)
    init.add_argument("--p1-state", type=Path, required=True)
    init.add_argument("--deck-request", type=Path, required=True)
    init.add_argument("--layout-requirements", type=Path, required=True)
    init.add_argument("--approved-outline", type=Path, required=True)
    init.add_argument("--slide-content-dir", type=Path, required=True)
    init.add_argument("--state", type=Path, required=True)
    init.add_argument("--absolute-host-model-invocation-ceiling", type=int)
    bypass = commands.add_parser("bypass")
    bypass.add_argument("--task-id", required=True)
    bypass.add_argument("--deck-id", required=True)
    bypass.add_argument("--state", type=Path, required=True)
    submit = commands.add_parser("submit-specs")
    submit.add_argument("--state", type=Path, required=True)
    submit.add_argument("--spec-dir", type=Path, required=True)
    submit.add_argument("--validation-report", type=Path, required=True)
    submit.add_argument("--pass-id", required=True)
    submit.add_argument("--host-model-invocation-id", required=True)
    submit.add_argument("--user-evidence-sha256")
    correction = commands.add_parser("apply-correction")
    correction.add_argument("--state", type=Path, required=True)
    correction.add_argument("--spec-dir", type=Path, required=True)
    correction.add_argument("--validation-report", type=Path, required=True)
    correction.add_argument("--correction", type=Path, required=True)
    correction.add_argument("--output-dir", type=Path, required=True)
    accept = commands.add_parser("accept-specs")
    accept.add_argument("--state", type=Path, required=True)
    accept.add_argument("--spec-dir", type=Path, required=True)
    accept.add_argument("--approved-outline", type=Path, required=True)
    accept.add_argument("--layout-requirements", type=Path, required=True)
    accept.add_argument("--output-ratio", choices=["16:9", "4:3"], required=True)
    accept.add_argument("--manifest-output", type=Path, required=True)
    accept.add_argument("--artifact-id", required=True)
    accept.add_argument("--revision", type=int, required=True)
    accept.add_argument("--previous-manifest", type=Path)
    accept.add_argument("--timestamp-utc")
    render = commands.add_parser("render")
    render.add_argument("--state", type=Path, required=True)
    render.add_argument("--manifest", type=Path, required=True)
    render.add_argument("--spec-dir", type=Path, required=True)
    render.add_argument("--slide-content-dir", type=Path, required=True)
    render.add_argument("--output-dir", type=Path, required=True)
    render.add_argument("--rendered-manifest-output", type=Path, required=True)
    preview = commands.add_parser("record-preview")
    preview.add_argument("--state", type=Path, required=True)
    preview.add_argument("--preview", type=Path, required=True)
    feedback = commands.add_parser("record-feedback")
    feedback.add_argument("--state", type=Path, required=True)
    feedback.add_argument("--feedback", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--state", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--spec-dir", type=Path, required=True)
    verify.add_argument("--slide-content-dir", type=Path, required=True)
    verify.add_argument("--wireframe-dir", type=Path, required=True)
    return result


def _init(args: argparse.Namespace) -> dict[str, Any]:
    if args.state.exists():
        raise ContractError([error("--state", "state already exists", "overwrite_forbidden")])
    bundle = load_authority_bundle(p1_state_path=args.p1_state.resolve(), deck_request_path=args.deck_request.resolve(), approved_outline_path=args.approved_outline.resolve(), slide_content_dir=args.slide_content_dir.resolve(), layout_requirements_path=args.layout_requirements.resolve())
    state = initial_state(task_id=args.task_id, deck_id=bundle["deck_request"]["deck_id"], absolute_host_model_invocation_ceiling=args.absolute_host_model_invocation_ceiling)
    state = advance(state, event="start_input_validation")
    state["current_artifacts"].update({
        "layout_requirements_sha256": canonical_sha256(bundle["layout_requirements"]),
        "approved_outline_sha256": canonical_sha256(bundle["approved_outline"]),
        "slide_content_manifest_sha256": canonical_sha256(bundle["projection_manifest"]),
    })
    state = advance(state, event="inputs_accepted")
    validate_schema("wireframe_state", state, SCHEMA_DIR)
    write_json(args.state.resolve(), state)
    return state


def _bypass(args: argparse.Namespace) -> dict[str, Any]:
    state = initial_state(task_id=args.task_id, deck_id=args.deck_id)
    state = advance(state, event="start_input_validation")
    state = advance(state, event="bypass_image_route")
    validate_schema("wireframe_state", state, SCHEMA_DIR)
    write_json(args.state.resolve(), state)
    return state


def _submit(args: argparse.Namespace) -> dict[str, Any]:
    state = load_json(args.state.resolve())
    _validate_state(state)
    specs = load_specs(args.spec_dir.resolve())
    report = load_json(args.validation_report.resolve())
    validate_schema("wireframe_validation_report", report, SCHEMA_DIR)
    digest = candidate_manifest_digest(specs)
    if report["candidate_manifest_sha256"] != digest or report["deck_id"] != state["deck_id"]:
        raise ContractError([error("--validation-report", "report does not bind Candidate Specs", "stale_validation_report")])
    if state["state"] == "candidate_specs_ready":
        if state["current_artifacts"]["candidate_manifest_sha256"] != digest:
            raise ContractError([error("--spec-dir", "corrected Candidate does not match State", "stale_candidate")])
        state = advance(state, event="start_spec_validation")
    elif state["state"] == "inputs_validated":
        state = advance(state, event="start_initial_planning", pass_id=args.pass_id, host_model_invocation_id=args.host_model_invocation_id)
        state = advance(state, event="candidate_specs_ready", artifact_kind="candidate_manifest", artifact_sha256=digest)
        state = advance(state, event="start_spec_validation")
    elif state["state"] == "revision_requested":
        state = advance(state, event="start_revision_planning", pass_id=args.pass_id, user_evidence_sha256=args.user_evidence_sha256, host_model_invocation_id=args.host_model_invocation_id)
        state = advance(state, event="candidate_specs_ready", artifact_kind="candidate_manifest", artifact_sha256=digest)
        state = advance(state, event="start_spec_validation")
    else:
        raise WireframeStateError(f"Spec submission is invalid from {state['state']}")
    if report["status"] == "pass":
        state = advance(state, event="specs_accepted")
    elif report["status"] == "correctable":
        state = advance(state, event="contract_correction_required")
    else:
        state = advance(state, event="fail", artifact_kind="candidate_manifest", artifact_sha256=digest)
    validate_schema("wireframe_state", state, SCHEMA_DIR)
    replace_json(args.state.resolve(), state)
    return state


def _correct(args: argparse.Namespace) -> dict[str, Any]:
    state = load_json(args.state.resolve())
    _validate_state(state)
    correction = load_json(args.correction.resolve())
    report = load_json(args.validation_report.resolve())
    state = advance(state, event="start_contract_correction", host_model_invocation_id=correction["host_model_invocation_id"])
    updated = apply_correction(specs=load_specs(args.spec_dir.resolve()), report=report, correction=correction)
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise ContractError([error("--output-dir", "Correction output directory must be empty", "overwrite_forbidden")])
    output.mkdir(parents=True, exist_ok=True)
    for spec in updated:
        write_json(output / f"{spec['slide_id']}-r{spec['revision']:03d}.json", spec)
    state = advance(state, event="contract_correction_applied", artifact_kind="candidate_manifest", artifact_sha256=candidate_manifest_digest(updated))
    validate_schema("wireframe_state", state, SCHEMA_DIR)
    replace_json(args.state.resolve(), state)
    return state


def _accept(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    state = load_json(args.state.resolve())
    _validate_state(state)
    if state["state"] != "specs_accepted":
        raise WireframeStateError("Manifest creation requires specs_accepted")
    approved = load_json(args.approved_outline.resolve())
    layout = load_json(args.layout_requirements.resolve())
    validate_schema("approved_outline", approved, SCHEMA_DIR)
    validate_schema("wireframe_layout_requirements", layout, SCHEMA_DIR)
    if approved["deck_id"] != state["deck_id"] or layout["deck_id"] != state["deck_id"]:
        raise ContractError([error("$", "Accepted Authority belongs to another Deck", "authority_identity_mismatch")])
    if canonical_sha256(approved) != state["current_artifacts"]["approved_outline_sha256"] or canonical_sha256(layout) != state["current_artifacts"]["layout_requirements_sha256"]:
        raise ContractError([error("$", "Accepted Authority does not match frozen P2 State", "authority_hash_mismatch")])
    previous = load_json(args.previous_manifest.resolve()) if args.previous_manifest else None
    manifest = build_manifest(approved_outline=approved, specs=load_specs(args.spec_dir.resolve()), layout_requirements=layout, output_ratio=args.output_ratio, artifact_id=args.artifact_id, revision=args.revision, parent_sha256=canonical_sha256(previous) if previous else None, previous_manifest=previous, created_at_utc=args.timestamp_utc)
    next_state = copy.deepcopy(state)
    next_state["current_artifacts"]["wireframe_manifest_sha256"] = canonical_sha256(manifest)
    validate_schema("wireframe_state", next_state, SCHEMA_DIR)
    write_json(args.manifest_output.resolve(), manifest)
    replace_json(args.state.resolve(), next_state)
    return next_state, manifest


def _render(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    state = load_json(args.state.resolve())
    _validate_state(state)
    manifest = load_json(args.manifest.resolve())
    validate_schema("wireframe_manifest", manifest, SCHEMA_DIR)
    if state["state"] != "specs_accepted" or state["current_artifacts"]["wireframe_manifest_sha256"] != canonical_sha256(manifest):
        raise WireframeStateError("render requires the current accepted Wireframe Manifest")
    projection, content_paths = _projection_bundle(state, args.slide_content_dir.resolve())
    specs = {item["slide_id"]: item for item in load_specs(args.spec_dir.resolve())}
    expected_slides = {item["slide_id"] for item in manifest["slides"]}
    if set(content_paths) != expected_slides or set(specs) != expected_slides:
        raise ContractError([error("$", "Manifest, Specs and Approved Content Slide IDs differ", "authority_identity_mismatch")])
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    state = advance(state, event="start_rendering")
    rendered_manifest = copy.deepcopy(manifest)
    page_results = []
    for item in rendered_manifest["slides"]:
        spec = specs[item["slide_id"]]
        target = output / f"{item['slide_id']}-r{spec['revision']:03d}.svg"
        if item["build_status"] == "reused" and item["svg_path"] and item["svg_sha256"]:
            reused = output / Path(item["svg_path"]).name
            if not reused.is_file() or hashlib.sha256(reused.read_bytes()).hexdigest() != item["svg_sha256"]:
                raise ContractError([error(str(reused), "reused SVG is unavailable or has changed", "reuse_evidence_missing")])
            target = reused
        else:
            if target.exists():
                raise ContractError([error(str(target), "Renderer refuses to overwrite SVG", "overwrite_forbidden")])
            svg, _warnings = render_document(spec, load_json(content_paths[item["slide_id"]]))
            target.write_bytes(svg)
            item["svg_path"] = f"wireframes/{target.name}"
            item["svg_sha256"] = hashlib.sha256(svg).hexdigest()
        page_results.append({"slide_id": item["slide_id"], "wireframe_input_sha256": item["wireframe_input_sha256"], "build_status": item["build_status"], "spec_sha256": item["spec_sha256"], "svg_sha256": item["svg_sha256"]})
    validate_schema("wireframe_manifest", rendered_manifest, SCHEMA_DIR)
    write_json(args.rendered_manifest_output.resolve(), rendered_manifest)
    state["page_results"] = page_results
    state["current_artifacts"]["wireframe_manifest_sha256"] = canonical_sha256(rendered_manifest)
    state = advance(state, event="rendering_complete", artifact_kind="wireframe_manifest", artifact_sha256=canonical_sha256(rendered_manifest))
    validate_schema("wireframe_state", state, SCHEMA_DIR)
    replace_json(args.state.resolve(), state)
    return state, rendered_manifest


def _preview(args: argparse.Namespace) -> dict[str, Any]:
    state = load_json(args.state.resolve())
    _validate_state(state)
    preview = load_json(args.preview.resolve())
    validate_schema("wireframe_preview", preview, SCHEMA_DIR)
    if state["state"] != "rendered":
        raise WireframeStateError("Preview recording requires rendered")
    if preview["deck_id"] != state["deck_id"]:
        raise ContractError([error("$.deck_id", "Preview belongs to another Deck", "deck_mismatch")])
    if preview["wireframe_manifest_sha256"] != state["current_artifacts"]["wireframe_manifest_sha256"]:
        raise ContractError([error("$.wireframe_manifest_sha256", "Preview does not bind current Manifest", "stale_preview")])
    if preview["mode"] == "internal_only" and (preview["visible_slide_ids"] or preview["presented_at_utc"] is not None or preview["pause_for_feedback"]):
        raise ContractError([error("$", "internal_only preview cannot be presented or paused", "invalid_preview")])
    if preview["mode"] == "user_visible" and (not preview["visible_slide_ids"] or preview["presented_at_utc"] is None):
        raise ContractError([error("$", "user_visible preview requires visible slides and presented_at_utc", "invalid_preview")])
    current_slides = {item["slide_id"] for item in state["page_results"]}
    if not set(preview["visible_slide_ids"]).issubset(current_slides):
        raise ContractError([error("$.visible_slide_ids", "Preview references unknown slides", "invalid_preview")])
    state = advance(state, event="preview_recorded", artifact_kind="preview", artifact_sha256=canonical_sha256(preview))
    state = advance(state, event="wait_for_feedback" if preview["pause_for_feedback"] else "complete_without_feedback")
    validate_schema("wireframe_state", state, SCHEMA_DIR)
    replace_json(args.state.resolve(), state)
    return state


def _feedback(args: argparse.Namespace) -> dict[str, Any]:
    state = load_json(args.state.resolve())
    _validate_state(state)
    feedback = load_json(args.feedback.resolve())
    validate_schema("wireframe_feedback", feedback, SCHEMA_DIR)
    if state["state"] != "awaiting_wireframe_feedback":
        raise WireframeStateError("Feedback requires awaiting_wireframe_feedback")
    if feedback["deck_id"] != state["deck_id"]:
        raise ContractError([error("$.deck_id", "Feedback belongs to another Deck", "deck_mismatch")])
    if feedback["wireframe_manifest_sha256"] != state["current_artifacts"]["wireframe_manifest_sha256"]:
        raise ContractError([error("$.wireframe_manifest_sha256", "Feedback does not bind current Manifest", "stale_feedback")])
    if feedback["wireframe_preview_sha256"] != state["current_artifacts"]["preview_sha256"]:
        raise ContractError([error("$.wireframe_preview_sha256", "Feedback does not bind current Preview", "stale_feedback")])
    current_slides = {item["slide_id"] for item in state["page_results"]}
    if not set(feedback["affected_slide_ids"]).issubset(current_slides):
        raise ContractError([error("$.affected_slide_ids", "Feedback references unknown slides", "invalid_feedback")])
    if feedback["decision"] == "changes_requested":
        if not feedback["affected_slide_ids"]:
            raise ContractError([error("$.affected_slide_ids", "changes_requested requires affected slides", "invalid_feedback")])
        if feedback["change_scope"] not in {"layout", "content"}:
            raise ContractError([error("$.change_scope", "changes_requested requires layout or content scope", "invalid_feedback")])
        event = "feedback_content_changes_requested" if feedback["change_scope"] == "content" else "feedback_changes_requested"
    else:
        if feedback["affected_slide_ids"] or feedback["change_scope"] != "none":
            raise ContractError([error("$", "accepted/continue requires no change scope or affected slides", "invalid_feedback")])
        event = "feedback_continue"
    feedback_hash = canonical_sha256(feedback)
    state = advance(state, event=event, artifact_kind="feedback", artifact_sha256=feedback_hash, user_evidence_sha256=feedback["user_message_sha256"], affected_slide_ids=feedback["affected_slide_ids"])
    validate_schema("wireframe_state", state, SCHEMA_DIR)
    replace_json(args.state.resolve(), state)
    return state


def _verify(args: argparse.Namespace) -> dict[str, Any]:
    state = load_json(args.state.resolve())
    _validate_state(state)
    if state["state"] == "p2_bypassed":
        return {"complete": True, "bypassed": True, "slides": 0}
    if state["state"] != "p2_complete":
        raise WireframeStateError("P2 verification requires p2_complete")
    manifest = load_json(args.manifest.resolve())
    validate_schema("wireframe_manifest", manifest, SCHEMA_DIR)
    if canonical_sha256(manifest) != state["current_artifacts"]["wireframe_manifest_sha256"]:
        raise ContractError([error("--manifest", "Manifest does not match State", "authority_hash_mismatch")])
    projection, content_paths = _projection_bundle(state, args.slide_content_dir.resolve())
    specs = {item["slide_id"]: item for item in load_specs(args.spec_dir.resolve())}
    expected_slides = {item["slide_id"] for item in manifest["slides"]}
    if set(content_paths) != expected_slides or set(specs) != expected_slides:
        raise ContractError([error("$", "Manifest, Specs and Approved Content Slide IDs differ", "authority_identity_mismatch")])
    for item in manifest["slides"]:
        if not item["svg_path"] or not is_safe_relative_path(item["svg_path"]):
            raise ContractError([error("$.slides.svg_path", "unsafe or missing SVG path", "invalid_manifest")])
        svg_path = args.wireframe_dir.resolve() / Path(item["svg_path"]).name
        content = svg_path.read_bytes()
        if hashlib.sha256(content).hexdigest() != item["svg_sha256"]:
            raise ContractError([error(str(svg_path), "SVG hash mismatch", "svg_hash_mismatch")])
        audit_svg(content, spec=specs[item["slide_id"]], slide_content=load_json(content_paths[item["slide_id"]]))
    return {"complete": True, "bypassed": False, "slides": len(manifest["slides"]), "host_model_invocations": state["counters"]["host_model_invocation_count"]}


def main() -> int:
    args = parser().parse_args()
    try:
        if args.action == "init":
            state, details = _init(args), {}
        elif args.action == "bypass":
            state, details = _bypass(args), {}
        elif args.action == "submit-specs":
            state, details = _submit(args), {}
        elif args.action == "apply-correction":
            state, details = _correct(args), {}
        elif args.action == "accept-specs":
            state, manifest = _accept(args)
            details = {"manifest_sha256": canonical_sha256(manifest)}
        elif args.action == "render":
            state, manifest = _render(args)
            details = {"manifest_sha256": canonical_sha256(manifest), "slides": len(manifest["slides"])}
        elif args.action == "record-preview":
            state, details = _preview(args), {}
        elif args.action == "record-feedback":
            state, details = _feedback(args), {}
        else:
            state = load_json(args.state.resolve())
            details = _verify(args)
        print(json.dumps({"status": "ok", "state": state["state"], "counters": state["counters"], **details}, ensure_ascii=False))
        return 0
    except (ContractError, WireframeStateError, FileNotFoundError) as exc:
        errors = exc.errors if isinstance(exc, ContractError) else [{"path": "$", "code": "wireframe_error", "message": str(exc)}]
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
