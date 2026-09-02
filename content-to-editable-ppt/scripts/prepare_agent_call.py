from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from agent_common import (
    REFERENCE_DIR,
    SCHEMA_DIR,
    SKILL_DIR,
    canonical_yaml_hash,
    copy_input,
    expected_call_dir,
    load_role,
    normalized_text_bytes,
    sha256_bytes,
    stage_directory,
)
from agent_request_evidence import input_manifest_entry
from asset_common import AssetError, atomic_write_bytes, atomic_write_json, failure, load_contract, log_event, sha256_file, success
from schema_utils import ContractError, load_json
from slide_size import resolve_slide_size


COMPONENT = "prepare_agent_call"


def _validate_content_authority(path: Path) -> None:
    document = load_json(path)
    items = document.get("text_items")
    if not isinstance(items, list) or not items:
        raise AssetError("content authority requires a non-empty text_items array", path=str(path), code="content_authority")
    ids: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or not isinstance(item.get("text"), str):
            raise AssetError("content authority text items require string id and text", path=f"$.text_items[{index}]", code="content_authority")
        if item["id"] in ids:
            raise AssetError("content authority IDs must be unique", path=f"$.text_items[{index}].id", code="content_authority")
        ids.add(item["id"])


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Create an isolated Planner or Reviewer call package.")
    result.add_argument("--role", choices=("planner", "reviewer"), required=True)
    result.add_argument("--mode", choices=("initial", "revision", "review"), required=True)
    result.add_argument("--work-root", type=Path, required=True)
    result.add_argument("--request", type=Path)
    result.add_argument("--source", type=Path)
    result.add_argument("--content-authority", type=Path)
    result.add_argument("--reconstruction-handoff", type=Path)
    result.add_argument("--slide-id")
    result.add_argument("--iteration-dir", type=Path)
    result.add_argument("--render", type=Path)
    result.add_argument("--layout", type=Path)
    result.add_argument("--qa-report", type=Path)
    result.add_argument("--asset-manifest", type=Path)
    result.add_argument("--iteration", type=int, required=True)
    result.add_argument(
        "--model-selection-mode",
        choices=("runtime-default", "explicit", "allowlist"),
        default="runtime-default",
    )
    result.add_argument("--requested-model")
    result.add_argument("--call-id", required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--run-id")
    result.add_argument("--log-file", type=Path)
    result.add_argument("--schema-dir", type=Path, default=SCHEMA_DIR)
    return result


def _inputs(args: argparse.Namespace) -> dict[str, Path]:
    schema = args.schema_dir.resolve()
    if args.role == "planner" and args.mode == "initial":
        if args.reconstruction_handoff is None:
            raise AssetError("Planner initial mode requires --reconstruction-handoff", path="--reconstruction-handoff", code="cli_error", exit_code=2)
        return {
            "request.json": args.request, "source.png": args.source,
            "reconstruction-handoff.json": args.reconstruction_handoff,
            "visual-spec.json": args.work_root / "visual-spec.json",
            "reconstruction-plan.schema.json": schema / "reconstruction-plan.schema.json",
            "element-classification.md": REFERENCE_DIR / "element-classification.md",
            "planner-response.schema.json": schema / "planner-response.schema.json",
        }
    if args.role == "planner" and args.mode == "revision":
        if args.iteration_dir is None or args.content_authority is None:
            raise AssetError("revision requires --iteration-dir and --content-authority", path="$", code="cli_error", exit_code=2)
        iteration = args.iteration_dir
        return {
            "request.json": args.request, "source.png": args.source, "source-content.json": args.content_authority,
            "layout.json": iteration / "layout.json", "crops.json": iteration / "crops.json",
            "asset_manifest.json": iteration / "asset_manifest.json", "qa_report.json": iteration / "qa_report.json",
            "review_report.json": iteration / "review_report.json", "review_evaluation.json": iteration / "review_evaluation.json",
            "review-patch.schema.json": schema / "review-patch.schema.json",
            "planner-response.schema.json": schema / "planner-response.schema.json",
        }
    if args.role == "reviewer" and args.mode == "review":
        required = (args.render, args.layout, args.qa_report, args.asset_manifest)
        if any(item is None for item in required):
            raise AssetError("review requires render, layout, QA report, and asset manifest", path="$", code="cli_error", exit_code=2)
        return {
            "request.json": args.request, "source.png": args.source, "rendered_slide.png": args.render,
            "layout.json": args.layout, "qa_report.json": args.qa_report, "asset_manifest.json": args.asset_manifest,
            "visual-review-rubric.md": REFERENCE_DIR / "visual-review-rubric.md",
            "reviewer-response.schema.json": schema / "reviewer-response.schema.json",
        }
    raise AssetError("role and mode are incompatible", path="--mode", code="cli_error", exit_code=2)


def main() -> int:
    args = parser().parse_args()
    run_id = args.run_id or "agent-call"
    try:
        if args.iteration < 1:
            raise AssetError("iteration must be provided", path="$", code="cli_error", exit_code=2)
        requested_model = args.requested_model.strip() if args.requested_model and args.requested_model.strip() else None
        if args.model_selection_mode == "runtime-default" and requested_model is not None:
            raise AssetError("runtime-default calls cannot request a model", path="--requested-model", code="cli_error", exit_code=2)
        if args.model_selection_mode == "explicit" and requested_model is None:
            raise AssetError("explicit calls require --requested-model", path="--requested-model", code="cli_error", exit_code=2)
        work_root = args.work_root.resolve()
        if args.request is None or args.source is None:
            raise AssetError("Planner and Reviewer modes require --request and --source", path="$", code="cli_error", exit_code=2)
        request_path = args.request.resolve()
        request = load_contract("request", request_path, args.schema_dir)
        resolve_slide_size(request["output_ratio"])
        task_id = request["task_id"]
        run_id = args.run_id or task_id
        if request_path.parent != work_root:
            raise AssetError("request must be directly inside work-root", path=str(request_path), code="path_escape")
        if args.source.resolve() != (work_root / request["source_image"]).resolve():
            raise AssetError("source does not match request source_image", path=str(args.source), code="input_mismatch")
        if args.role == "planner" and args.mode == "revision":
            authority = args.content_authority.resolve() if args.content_authority else None
            if authority is None or authority.parent != work_root or authority.name != "source-content.json":
                raise AssetError("Planner content authority must be work-root/source-content.json", path="--content-authority", code="path_escape")
            _validate_content_authority(authority)
        if args.role == "planner" and args.mode == "initial":
            if not args.slide_id:
                raise AssetError("Planner initial mode requires --slide-id", path="--slide-id", code="cli_error", exit_code=2)
            handoff_path = args.reconstruction_handoff.resolve() if args.reconstruction_handoff else None
            expected_handoff = work_root / "reconstruction-handoff.json"
            if handoff_path != expected_handoff or not expected_handoff.is_file():
                raise AssetError("reconstruction handoff must be work-root/reconstruction-handoff.json", path="--reconstruction-handoff", code="path_escape")
            handoff = load_contract("reconstruction_handoff", handoff_path, args.schema_dir)
            if handoff["slide_id"] != args.slide_id:
                raise AssetError("slide-id does not match reconstruction handoff", path="--slide-id", code="page_identity_mismatch", exit_code=9)
            if handoff["stage2"]["approved_design"] != request["source_image"]:
                raise AssetError("handoff Approved Design does not match request source_image", path="$.stage2.approved_design", code="source_mismatch")
            if sha256_file(args.source.resolve()) != handoff["provenance"]["approved_design_sha256"]:
                raise AssetError("Approved Design changed after Handoff materialization", path=str(args.source), code="approved_design_changed", exit_code=9)
            visual_spec_path = work_root / handoff["stage2"]["visual_spec"]
            if visual_spec_path != work_root / "visual-spec.json" or not visual_spec_path.is_file():
                raise AssetError("visual spec must be work-root/visual-spec.json", path="$.stage2.visual_spec", code="missing_input", exit_code=3)
            try:
                load_json(visual_spec_path)
            except (json.JSONDecodeError, UnicodeError, ContractError) as exc:
                raise AssetError("visual spec must be a UTF-8 JSON object", path=str(visual_spec_path), code="invalid_visual_spec") from exc
            if sha256_file(visual_spec_path) != handoff["provenance"]["visual_spec_sha256"]:
                raise AssetError("Visual Spec changed after Handoff materialization", path=str(visual_spec_path), code="visual_spec_changed", exit_code=9)
        expected_output = expected_call_dir(work_root, args.iteration, args.role, args.call_id)
        if args.output_dir.resolve() != expected_output:
            raise AssetError("output-dir must match .agent-calls/<iteration>/<role>/<call-id>", path=str(args.output_dir), code="path_escape")
        if expected_output.exists():
            raise AssetError("call directory already exists", path=str(expected_output), code="output_conflict", exit_code=9)
        if args.iteration_dir is not None:
            expected_iteration = work_root / "iterations" / f"{args.iteration:02d}"
            if args.iteration_dir.resolve() != expected_iteration or not expected_iteration.is_dir():
                raise AssetError("iteration-dir does not match work-root and iteration", path=str(args.iteration_dir), code="iteration_mismatch")
        if args.role == "reviewer":
            expected_iteration = work_root / "iterations" / f"{args.iteration:02d}"
            expected_paths = {
                "render": expected_iteration / "rendered_slide.png", "layout": expected_iteration / "layout.json",
                "qa-report": expected_iteration / "qa_report.json", "asset-manifest": expected_iteration / "asset_manifest.json",
            }
            actual_paths = {"render": args.render, "layout": args.layout, "qa-report": args.qa_report, "asset-manifest": args.asset_manifest}
            for label, expected_path in expected_paths.items():
                if actual_paths[label] is None or actual_paths[label].resolve() != expected_path.resolve():
                    raise AssetError(f"{label} must be the current iteration artifact", path=f"--{label}", code="path_escape")

        config, config_path, prompt_path, output_schema = load_role(args.role, args.schema_dir, mode=args.mode)
        inputs = _inputs(args)
        if list(inputs) != config["input_profiles"][args.mode]:
            raise AssetError("implementation allowlist differs from role configuration", path=str(config_path), code="agent_config", exit_code=2)
        stage = stage_directory(expected_output)
        try:
            prompt = normalized_text_bytes(prompt_path)
            atomic_write_bytes(stage / "system_prompt.md", prompt)
            entries = []
            for name, source in inputs.items():
                authorized = None if source.resolve().is_relative_to(SKILL_DIR.resolve()) else work_root
                digest = copy_input(source, stage / "inputs" / name, authorized_root=authorized)
                entries.append(input_manifest_entry(name, digest))
            schema_hash = next(item["sha256"] for item in entries if item["name"] == output_schema.name)
            manifest = {
                "schema_version": "1.3", "task_id": task_id, "iteration": args.iteration,
                "role": args.role, "mode": args.mode,
                "model_selection_mode": args.model_selection_mode,
                "requested_model": requested_model,
                "call_id": args.call_id,
                "context_policy": "fresh", "parent_context_id": None,
                "role_version": config["role_version"], "parameters": config["parameters"],
                "config_sha256": canonical_yaml_hash(config_path),
                "prompt_sha256": sha256_bytes(prompt), "output_schema_sha256": schema_hash,
                "input_profile": args.mode,
                "selected_output_schema": output_schema.name,
                "selected_output_schema_sha256": schema_hash,
                "inputs": entries,
            }
            if args.role == "planner" and args.mode == "initial":
                manifest["slide_id"] = args.slide_id
            atomic_write_json(stage / "call_manifest.json", manifest)
            os.replace(stage, expected_output)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        log_event(args.log_file, level="info", component=COMPONENT, event="completed", message="Agent call package created", run_id=run_id, iteration=args.iteration, data={"role": args.role, "mode": args.mode})
        return success(COMPONENT, {"call_dir": str(expected_output), "call_manifest": str(expected_output / "call_manifest.json")}, run_id=run_id, iteration=args.iteration)
    except Exception as exc:
        log_event(args.log_file, level="error", component=COMPONENT, event="failed", message=str(exc), run_id=run_id, iteration=args.iteration, data={"exit_code": getattr(exc, "exit_code", 70)})
        return failure(COMPONENT, exc, run_id=run_id, iteration=args.iteration)


if __name__ == "__main__":
    raise SystemExit(main())
