from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from markdown_wireframe import SCHEMA_DIR, audit_markdown, bind_markdown, build_validation_report, load_markdown_authority, sha256_bytes, utc_now
from schema_utils import ContractError, error, load_json, validate_schema
from wireframe_state import WireframeStateError, consume_correction, initial_state, mark_bound, record_feedback, record_preview, request_visual_revision, submit_validation


def _bytes_json(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ContractError([error(str(path), "refusing to overwrite existing artifact", "overwrite_forbidden")])
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _replace(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _load_state(path: Path) -> dict[str, Any]:
    document = load_json(path)
    validate_schema("markdown_wireframe_state", document, SCHEMA_DIR)
    return document


def _replace_state(path: Path, state: dict[str, Any]) -> None:
    validate_schema("markdown_wireframe_state", state, SCHEMA_DIR)
    _replace(path, _bytes_json(state))


def _manifest_path(root: Path, revision: int, *, accepted: bool = False) -> Path:
    name = "wireframe-manifest.json" if accepted else "preview-manifest.json"
    return root / "revisions" / f"r{revision:03d}" / name


def _commit_revision(root: Path, revision: int, *, candidate: dict[str, Any], markdown: bytes, manifest: dict[str, Any]) -> None:
    final = root / "revisions" / f"r{revision:03d}"
    expected = {
        "candidate.json": _bytes_json(candidate),
        "deck-wireframe.md": markdown,
        "preview-manifest.json": _bytes_json(manifest),
    }
    if final.exists():
        if all((final / name).is_file() and (final / name).read_bytes() == data for name, data in expected.items()):
            return
        raise ContractError([error(str(final), "revision already exists with different bytes", "overwrite_forbidden")])
    staging = final.with_name(final.name + ".tmp")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        for name, data in expected.items():
            (staging / name).write_bytes(data)
        os.replace(staging, final)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _publish(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    revision_dir = root / "revisions" / f"r{state['current_revision']:03d}"
    markdown_path = revision_dir / "deck-wireframe.md"
    preview_manifest = load_json(revision_dir / "preview-manifest.json")
    if sha256_bytes(markdown_path.read_bytes()) != preview_manifest["wireframe_sha256"]:
        raise ContractError([error(str(markdown_path), "revision Markdown hash mismatch", "markdown_hash_mismatch")])
    accepted = copy.deepcopy(preview_manifest)
    accepted["status"] = "accepted"
    validate_schema("markdown_wireframe_manifest", accepted, SCHEMA_DIR)
    accepted_path = _manifest_path(root, state["current_revision"], accepted=True)
    accepted_bytes = _bytes_json(accepted)
    if accepted_path.exists():
        if accepted_path.read_bytes() != accepted_bytes:
            raise ContractError([error(str(accepted_path), "accepted revision manifest differs from recovery input", "overwrite_forbidden")])
    else:
        _write_once(accepted_path, accepted_bytes)
    _replace(root / "deck-wireframe.md", markdown_path.read_bytes())
    _replace(root / "wireframe-manifest.json", accepted_bytes)
    result = copy.deepcopy(state)
    result["current_artifacts"]["wireframe_manifest_sha256"] = canonical_sha256(accepted)
    return result


def _json_pointer(document: Any, path: str) -> tuple[Any, str]:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")[1:]]
    target = document
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    return target, parts[-1]


def _apply_patch(candidate: dict[str, Any], report: dict[str, Any], correction: dict[str, Any]) -> dict[str, Any]:
    validate_schema("markdown_wireframe_correction_record", correction, SCHEMA_DIR)
    if correction["candidate_sha256"] != canonical_sha256(candidate) or correction["validation_report_sha256"] != canonical_sha256(report):
        raise ContractError([error("$", "Correction does not bind Candidate and Validation Report", "stale_correction")])
    issues = {item["issue_id"]: item for item in report["issues"] if item["correctable"]}
    result = copy.deepcopy(candidate)
    for operation in correction["operations"]:
        issue = issues.get(operation["validation_issue_id"])
        if issue is None:
            raise ContractError([error("$.operations", "operation is not bound to a correctable issue", "correction_not_allowed")])
        target, key = _json_pointer(result, operation["path"])
        exists = (int(key) < len(target)) if isinstance(target, list) and key.isdigit() else (key in target if isinstance(target, dict) else False)
        current = target[int(key)] if isinstance(target, list) and exists else (target[key] if isinstance(target, dict) and exists else None)
        if current != operation["before"]:
            raise ContractError([error(operation["path"], "Correction before value is stale", "stale_before_value")])
        if operation["op"] == "remove":
            (target.pop(int(key)) if isinstance(target, list) else target.pop(key))
        elif operation["op"] == "add":
            if exists:
                raise ContractError([error(operation["path"], "add target already exists", "correction_not_allowed")])
            (target.insert(int(key), operation["after"]) if isinstance(target, list) else target.__setitem__(key, operation["after"]))
        else:
            if not exists:
                raise ContractError([error(operation["path"], "replace target is missing", "correction_not_allowed")])
            if isinstance(target, list): target[int(key)] = operation["after"]
            else: target[key] = operation["after"]
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Manage P2 model-generated Markdown wireframes")
    commands = result.add_subparsers(dest="action", required=True)
    init = commands.add_parser("init")
    init.add_argument("--task-id", required=True); init.add_argument("--p1-state", type=Path, required=True)
    init.add_argument("--approved-outline", type=Path, required=True); init.add_argument("--slide-content-dir", type=Path, required=True)
    init.add_argument("--wireframe-root", type=Path, required=True); init.add_argument("--state", type=Path, required=True)
    init.add_argument("--absolute-host-model-invocation-ceiling", type=int)
    submit = commands.add_parser("submit-candidate")
    submit.add_argument("--state", type=Path, required=True); submit.add_argument("--candidate", type=Path, required=True)
    submit.add_argument("--approved-outline", type=Path, required=True); submit.add_argument("--slide-content-dir", type=Path, required=True)
    submit.add_argument("--validation-report", type=Path, required=True); submit.add_argument("--user-evidence-sha256")
    submit.add_argument("--wireframe-root", type=Path)
    correct = commands.add_parser("apply-correction")
    correct.add_argument("--state", type=Path, required=True); correct.add_argument("--candidate", type=Path, required=True)
    correct.add_argument("--validation-report", type=Path, required=True); correct.add_argument("--correction", type=Path, required=True)
    correct.add_argument("--output", type=Path, required=True)
    bind = commands.add_parser("bind")
    bind.add_argument("--state", type=Path, required=True); bind.add_argument("--candidate", type=Path, required=True)
    bind.add_argument("--approved-outline", type=Path, required=True); bind.add_argument("--slide-content-dir", type=Path, required=True)
    bind.add_argument("--wireframe-root", type=Path, required=True)
    preview = commands.add_parser("record-preview")
    preview.add_argument("--state", type=Path, required=True); preview.add_argument("--wireframe-root", type=Path, required=True)
    preview.add_argument("--mode", choices=["user_visible", "skipped"], required=True); preview.add_argument("--user-message-sha256", required=True)
    feedback = commands.add_parser("record-feedback")
    feedback.add_argument("--state", type=Path, required=True); feedback.add_argument("--wireframe-root", type=Path, required=True)
    feedback.add_argument("--feedback", type=Path, required=True)
    revise = commands.add_parser("request-visual-revision")
    revise.add_argument("--state", type=Path, required=True); revise.add_argument("--wireframe-root", type=Path, required=True)
    revise.add_argument("--feedback", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--state", type=Path, required=True); verify.add_argument("--approved-outline", type=Path, required=True)
    verify.add_argument("--slide-content-dir", type=Path, required=True); verify.add_argument("--wireframe-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.action == "init":
            if args.state.resolve().exists(): raise ContractError([error("--state", "state already exists", "overwrite_forbidden")])
            bundle = load_markdown_authority(p1_state_path=args.p1_state.resolve(), approved_outline_path=args.approved_outline.resolve(), slide_content_dir=args.slide_content_dir.resolve())
            state = initial_state(task_id=args.task_id, deck_id=bundle["approved_outline"]["deck_id"], approved_outline_sha256=canonical_sha256(bundle["approved_outline"]), slide_content_manifest_sha256=canonical_sha256(bundle["projection_manifest"]), absolute_host_model_invocation_ceiling=args.absolute_host_model_invocation_ceiling)
            _write_once(args.state.resolve(), _bytes_json(state)); details = {}
        else:
            state = _load_state(args.state.resolve())
            if args.action == "submit-candidate":
                # P1 State is intentionally not stored as a path. Reconstruct the real Authority check from frozen hashes.
                approved, projection = load_json(args.approved_outline.resolve()), load_json(args.slide_content_dir.resolve() / "projection-manifest.json")
                if canonical_sha256(approved) != state["current_artifacts"]["approved_outline_sha256"] or canonical_sha256(projection) != state["current_artifacts"]["slide_content_manifest_sha256"]:
                    raise ContractError([error("$", "actual P1 Authority differs from initialized P2 State", "authority_hash_mismatch")])
                bundle = load_markdown_authority(approved_outline_path=args.approved_outline.resolve(), slide_content_dir=args.slide_content_dir.resolve(), frozen_outline_sha256=state["current_artifacts"]["approved_outline_sha256"], frozen_manifest_sha256=state["current_artifacts"]["slide_content_manifest_sha256"], expected_deck_id=state["deck_id"])
                candidate = load_json(args.candidate.resolve())
                if state["state"] == "revision_requested":
                    if args.wireframe_root is None:
                        raise ContractError([error("--wireframe-root", "revision submission requires the immutable previous Candidate", "missing_authority")])
                    previous_path = args.wireframe_root.resolve() / "revisions" / f"r{state['current_revision']:03d}" / "candidate.json"
                    previous = load_json(previous_path)
                    previous_by_id = {slide["slide_id"]: slide for slide in previous["slides"]}
                    changed = set(state["changed_slide_ids"])
                    if candidate["revision"] != state["current_revision"] + 1 or candidate["parent_sha256"] != canonical_sha256(previous):
                        raise ContractError([error("$", "revision Candidate does not bind its immutable parent", "stale_revision")])
                    for slide in candidate["slides"]:
                        old = previous_by_id.get(slide["slide_id"])
                        if old is None:
                            continue
                        if slide["slide_id"] not in changed and slide != old:
                            raise ContractError([error(f"$.slides.{slide['slide_id']}", "unchanged slide differs from prior Revision", "revision_scope_mismatch")])
                        if slide["slide_id"] in changed:
                            for key in {"slide_id", "order", "content_labels"}:
                                if slide[key] != old[key]:
                                    raise ContractError([error(f"$.slides.{slide['slide_id']}.{key}", "visual revision cannot change content identity or order", "revision_scope_mismatch")])
                candidate_version = candidate.get("schema_version")
                if state["state"] == "revision_requested" and candidate_version != "1.2":
                    raise ContractError([error("$.schema_version", "Visual Storyboard Revision requires Candidate 1.2", "unsupported_schema_version")])
                required_storyboards = set(state["changed_slide_ids"]) if state["state"] == "revision_requested" else None
                report = build_validation_report(candidate, bundle, report_id=f"{candidate['artifact_id']}-validation", storyboard_required_slide_ids=required_storyboards)
                _write_once(args.validation_report.resolve(), _bytes_json(report))
                state = submit_validation(state, candidate_sha256=canonical_sha256(candidate), report_sha256=canonical_sha256(report), status=report["status"], host_model_invocation_id=candidate["host_model_invocation_id"], pass_id=candidate["pass_id"], user_evidence_sha256=args.user_evidence_sha256)
                _replace_state(args.state.resolve(), state); details = {"validation_status": report["status"]}
            elif args.action == "apply-correction":
                candidate, report, correction = load_json(args.candidate.resolve()), load_json(args.validation_report.resolve()), load_json(args.correction.resolve())
                state = consume_correction(state, host_model_invocation_id=correction["host_model_invocation_id"])
                corrected = _apply_patch(candidate, report, correction); validate_schema("markdown_wireframe_candidate", corrected, SCHEMA_DIR)
                _write_once(args.output.resolve(), _bytes_json(corrected)); _replace_state(args.state.resolve(), state); details = {"candidate_sha256": canonical_sha256(corrected)}
            elif args.action == "bind":
                candidate, approved, projection = load_json(args.candidate.resolve()), load_json(args.approved_outline.resolve()), load_json(args.slide_content_dir.resolve() / "projection-manifest.json")
                if canonical_sha256(candidate) != state["current_artifacts"]["candidate_sha256"] or canonical_sha256(approved) != state["current_artifacts"]["approved_outline_sha256"] or canonical_sha256(projection) != state["current_artifacts"]["slide_content_manifest_sha256"]:
                    raise ContractError([error("$", "bind inputs do not match State", "authority_hash_mismatch")])
                bundle = load_markdown_authority(approved_outline_path=args.approved_outline.resolve(), slide_content_dir=args.slide_content_dir.resolve(), frozen_outline_sha256=state["current_artifacts"]["approved_outline_sha256"], frozen_manifest_sha256=state["current_artifacts"]["slide_content_manifest_sha256"], expected_deck_id=state["deck_id"])
                required_storyboards = set(state["changed_slide_ids"]) if state["changed_slide_ids"] else None
                markdown, manifest = bind_markdown(candidate, bundle, storyboard_required_slide_ids=required_storyboards); revision = state["current_revision"] + 1; manifest["revision"] = revision
                next_state = mark_bound(state, revision=revision, manifest_sha256=canonical_sha256(manifest), wireframe_sha256=manifest["wireframe_sha256"])
                validate_schema("markdown_wireframe_state", next_state, SCHEMA_DIR)
                _commit_revision(args.wireframe_root.resolve(), revision, candidate=candidate, markdown=markdown, manifest=manifest)
                state = next_state; _replace_state(args.state.resolve(), state); details = {"revision": revision, "wireframe_sha256": manifest["wireframe_sha256"]}
            elif args.action == "record-preview":
                manifest = load_json(_manifest_path(args.wireframe_root.resolve(), state["current_revision"])); slide_ids = [item["slide_id"] for item in manifest["slides"]]
                preview = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_type": "markdown_wireframe_preview", "preview_id": f"{state['deck_id']}-r{state['current_revision']:03d}-preview", "deck_id": state["deck_id"], "revision": state["current_revision"], "wireframe_manifest_sha256": canonical_sha256(manifest), "mode": args.mode, "visible_slide_ids": slide_ids if args.mode == "user_visible" else [], "pause_for_feedback": args.mode == "user_visible", "user_message_sha256": args.user_message_sha256, "created_at_utc": utc_now()}
                validate_schema("markdown_wireframe_preview", preview, SCHEMA_DIR); _write_once(args.wireframe_root.resolve() / "revisions" / f"r{state['current_revision']:03d}" / "preview.json", _bytes_json(preview))
                state = record_preview(state, preview_sha256=canonical_sha256(preview), mode=args.mode, user_message_sha256=args.user_message_sha256)
                if args.mode == "skipped": state = _publish(args.wireframe_root.resolve(), state)
                _replace_state(args.state.resolve(), state); details = {"preview_sha256": canonical_sha256(preview)}
            elif args.action in {"record-feedback", "request-visual-revision"}:
                feedback = load_json(args.feedback.resolve()); validate_schema("markdown_wireframe_feedback", feedback, SCHEMA_DIR)
                manifest_path = args.wireframe_root.resolve() / "wireframe-manifest.json" if args.action == "request-visual-revision" else _manifest_path(args.wireframe_root.resolve(), state["current_revision"])
                manifest = load_json(manifest_path); valid_ids = {item["slide_id"] for item in manifest["slides"]}
                if feedback["deck_id"] != state["deck_id"] or feedback["revision"] != state["current_revision"] or feedback["wireframe_manifest_sha256"] != canonical_sha256(manifest) or feedback["preview_sha256"] != state["current_artifacts"]["preview_sha256"]:
                    raise ContractError([error("$", "Feedback does not bind current preview", "stale_feedback")])
                affected = feedback["affected_slide_ids"]
                if not set(affected).issubset(valid_ids) or (feedback["decision"] == "changes_requested") != bool(affected) or ((feedback["decision"] in {"accepted", "continue"}) != (feedback["change_scope"] == "none")):
                    raise ContractError([error("$", "Feedback scope is invalid", "invalid_feedback")])
                if args.action == "request-visual-revision":
                    if feedback["decision"] != "changes_requested" or feedback["change_scope"] != "visual_storyboard":
                        raise ContractError([error("$", "request-visual-revision requires changes_requested + visual_storyboard", "invalid_feedback")])
                    state = request_visual_revision(state, feedback_sha256=canonical_sha256(feedback), affected_slide_ids=affected, user_message_sha256=feedback["user_message_sha256"])
                    feedback_name = "visual-storyboard-revision-request.json"
                else:
                    state = record_feedback(state, feedback_sha256=canonical_sha256(feedback), decision=feedback["decision"], scope=feedback["change_scope"], affected_slide_ids=affected, user_message_sha256=feedback["user_message_sha256"])
                    feedback_name = "feedback.json"
                _write_once(args.wireframe_root.resolve() / "revisions" / f"r{state['current_revision']:03d}" / feedback_name, _bytes_json(feedback))
                if state["state"] == "p2_complete": state = _publish(args.wireframe_root.resolve(), state)
                _replace_state(args.state.resolve(), state); details = {"feedback_sha256": canonical_sha256(feedback)}
            else:
                if state["state"] != "p2_complete": raise WireframeStateError("verify requires p2_complete")
                approved, projection = load_json(args.approved_outline.resolve()), load_json(args.slide_content_dir.resolve() / "projection-manifest.json")
                manifest = load_json(args.wireframe_root.resolve() / "wireframe-manifest.json"); markdown = (args.wireframe_root.resolve() / "deck-wireframe.md").read_bytes()
                if canonical_sha256(approved) != state["current_artifacts"]["approved_outline_sha256"] or canonical_sha256(projection) != state["current_artifacts"]["slide_content_manifest_sha256"] or canonical_sha256(manifest) != state["current_artifacts"]["wireframe_manifest_sha256"]:
                    raise ContractError([error("$", "published Authority does not match State", "authority_hash_mismatch")])
                bundle = load_markdown_authority(approved_outline_path=args.approved_outline.resolve(), slide_content_dir=args.slide_content_dir.resolve(), frozen_outline_sha256=state["current_artifacts"]["approved_outline_sha256"], frozen_manifest_sha256=state["current_artifacts"]["slide_content_manifest_sha256"], expected_deck_id=state["deck_id"])
                audit_markdown(markdown, manifest, bundle)
                details = {"complete": True, "revision": state["current_revision"], "slides": len(manifest["slides"])}
        print(json.dumps({"status": "ok", "state": state["state"], "counters": state["counters"], **details}, ensure_ascii=False)); return 0
    except (ContractError, WireframeStateError, FileNotFoundError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        errors = exc.errors if isinstance(exc, ContractError) else [{"path": "$", "code": "wireframe_error", "message": str(exc)}]
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False)); return 4


if __name__ == "__main__":
    raise SystemExit(main())
