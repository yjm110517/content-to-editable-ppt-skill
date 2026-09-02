from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

from agent_common import SCHEMA_DIR, load_call_bundle, provenance_entry, stage_directory
from asset_common import AssetError, atomic_write_json, failure, load_contract, log_event, sha256_file, success
from compile_reconstruction_plan import read_source_metadata
from reconstruction_plan import compile_reconstruction_plan
from schema_utils import ContractError, load_json, validate_schema, validate_semantics
from shared_validator import validate_documents
from visual_first_planner import (
    canonicalize_plan_for_runtime,
    content_authority_from_handoff,
    validate_block_against_handoff,
    validate_content_projection,
    validate_plan_against_handoff,
)


COMPONENT = "finalize_agent_response"
def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate and atomically submit Planner or Reviewer output.")
    result.add_argument("--role", choices=("planner", "reviewer"), required=True)
    result.add_argument("--mode", choices=("initial", "revision", "review"), required=True)
    result.add_argument("--call-dir", type=Path, required=True)
    result.add_argument("--planner-call-record", type=Path)
    result.add_argument("--iteration-dir", type=Path)
    result.add_argument("--output-dir", type=Path)
    result.add_argument("--output", type=Path)
    result.add_argument("--run-id", required=True)
    result.add_argument("--iteration", type=int, required=True)
    result.add_argument("--log-file", type=Path)
    result.add_argument("--schema-dir", type=Path, default=SCHEMA_DIR)
    return result


def _work_root(args: argparse.Namespace) -> Path:
    if args.role == "planner" and args.mode == "initial":
        if args.output_dir is None:
            raise AssetError("initial mode requires --output-dir", path="--output-dir", code="cli_error", exit_code=2)
        output = args.output_dir.resolve()
        if output.parent.name != "iterations" or output.name != f"{args.iteration:02d}":
            raise AssetError("output-dir must be work-root/iterations/<NN>", path=str(output), code="path_escape")
        return output.parent.parent
    if args.iteration_dir is None:
        raise AssetError("mode requires --iteration-dir", path="--iteration-dir", code="cli_error", exit_code=2)
    iteration = args.iteration_dir.resolve()
    if iteration.parent.name != "iterations" or iteration.name != f"{args.iteration:02d}":
        raise AssetError("iteration-dir must be work-root/iterations/<NN>", path=str(iteration), code="path_escape")
    return iteration.parent.parent


def _load_call_input(call_dir: Path, name: str) -> dict[str, Any]:
    return load_json(call_dir / "inputs" / name)


def _validate_identity(response: dict[str, Any], manifest: dict[str, Any], iteration: int) -> None:
    if response["task_id"] != manifest["task_id"] or response["iteration"] != iteration:
        raise AssetError("agent response task or iteration mismatch", path=str(manifest), code="iteration_mismatch", exit_code=9)


def _validate_no_full_page_raster(layout: dict[str, Any], crops: dict[str, Any], manifest: dict[str, Any]) -> None:
    crop_by_id = {item["id"]: item for item in crops["assets"]}
    manifest_by_id = {item["id"]: item for item in manifest["assets"]}
    slide_area = layout["slide"]["width_in"] * layout["slide"]["height_in"]
    source_area = layout["source"]["width_px"] * layout["source"]["height_px"]
    for element in layout["elements"]:
        if element["type"] != "image" or element["w"] * element["h"] < slide_area * 0.95:
            continue
        asset = manifest_by_id.get(element.get("asset_id"))
        crop = crop_by_id.get(element.get("asset_id"))
        if asset and asset["type"] in {"png", "jpeg"} and crop:
            left, top, right, bottom = crop["box_px"]
            if (right - left) * (bottom - top) >= source_area * 0.95:
                raise AssetError("full-page source raster cannot be used as a slide-sized image", path=f"layout.elements.{element['id']}", code="prompt_injection_guard")


def _first_contract_error(exc: ContractError) -> AssetError:
    detail = exc.errors[0] if exc.errors else {"path": "$", "code": "contract_error", "message": str(exc)}
    return AssetError(detail["message"], path=detail["path"], code=detail["code"])


def _finalize_initial(
    args: argparse.Namespace,
    manifest: dict[str, Any],
    response: dict[str, Any],
) -> dict[str, Any]:
    output = args.output_dir.resolve()
    if output.exists():
        raise AssetError("iteration already exists", path=str(output), code="output_conflict", exit_code=9)

    request = _load_call_input(args.call_dir, "request.json")
    handoff = _load_call_input(args.call_dir, "reconstruction-handoff.json")
    slide_id = manifest.get("slide_id")
    if not isinstance(slide_id, str) or not slide_id:
        raise AssetError("Planner call manifest is missing slide_id", path="$.slide_id", code="call_bundle", exit_code=9)

    if response["outcome"] == "block":
        try:
            validate_block_against_handoff(response["block"], handoff)
        except ContractError as exc:
            raise _first_contract_error(exc) from exc
        return {
            "planner_status": "blocked",
            "block": response["block"],
            "call_dir": str(args.call_dir),
        }

    candidate_plan = response["artifacts"]["reconstruction_plan"]
    try:
        # Candidate validation deliberately excludes the exact Runtime slide-size gate.
        validate_schema("reconstruction_plan", candidate_plan, args.schema_dir)
        validate_semantics("reconstruction_plan", candidate_plan)
        validate_plan_against_handoff(
            candidate_plan,
            handoff,
            request,
            iteration=args.iteration,
            slide_id=slide_id,
        )
        plan = canonicalize_plan_for_runtime(candidate_plan, request)
        # Canonical validation runs again after deterministic Runtime normalization.
        validate_schema("reconstruction_plan", plan, args.schema_dir)
        validate_semantics("reconstruction_plan", plan)
        work_root = output.parent.parent
        projection_path = work_root / "source-content.json"
        if not projection_path.is_file():
            raise AssetError("source-content compatibility projection is missing", path=str(projection_path), code="missing_input", exit_code=3)
        try:
            projection = load_json(projection_path)
        except (json.JSONDecodeError, UnicodeError, ContractError) as exc:
            raise AssetError("source-content compatibility projection is invalid", path=str(projection_path), code="content_projection_mismatch") from exc
        validate_content_projection(handoff, projection)
        authority = content_authority_from_handoff(handoff)
        source = work_root / request["source_image"]
        artifacts = compile_reconstruction_plan(plan, authority, request, read_source_metadata(source))
        paths = {
            "layout": output / "layout.json",
            "crops": output / "crops.json",
            "asset_manifest": output / "asset_manifest.json",
        }
        validate_documents(artifacts, paths, profile="candidate", schema_dir=args.schema_dir)
        _validate_no_full_page_raster(artifacts["layout"], artifacts["crops"], artifacts["asset_manifest"])
    except ContractError as exc:
        raise _first_contract_error(exc) from exc

    stage = stage_directory(output)
    try:
        atomic_write_json(stage / "reconstruction-plan.json", plan)
        atomic_write_json(stage / "layout.json", artifacts["layout"])
        atomic_write_json(stage / "crops.json", artifacts["crops"])
        atomic_write_json(stage / "asset_manifest.json", artifacts["asset_manifest"])
        os.replace(stage, output)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {
        "planner_status": "planned",
        "iteration_dir": str(output),
        "reconstruction_plan": str(output / "reconstruction-plan.json"),
        "layout": str(output / "layout.json"),
        "crops": str(output / "crops.json"),
        "asset_manifest": str(output / "asset_manifest.json"),
    }


def _verify_current_inputs(iteration_dir: Path, input_hashes: dict[str, str], names: list[str]) -> None:
    for name in names:
        actual = iteration_dir / name
        if not actual.is_file() or sha256_file(actual) != input_hashes[name]:
            raise AssetError("current iteration input changed after Agent call", path=str(actual), code="hash_conflict", exit_code=9)


def _verify_work_inputs(call_dir: Path, work_root: Path, input_hashes: dict[str, str]) -> None:
    request_copy = _load_call_input(call_dir, "request.json")
    current = {"request.json": work_root / "request.json", "source.png": work_root / request_copy["source_image"]}
    if "reconstruction-handoff.json" in input_hashes:
        current["reconstruction-handoff.json"] = work_root / "reconstruction-handoff.json"
    if "visual-spec.json" in input_hashes:
        current["visual-spec.json"] = work_root / "visual-spec.json"
    for name, path in current.items():
        if not path.is_file() or sha256_file(path) != input_hashes[name]:
            raise AssetError("work input changed after Agent call", path=str(path), code="hash_conflict", exit_code=9)


def _finalize_revision(args: argparse.Namespace, manifest: dict[str, Any], response: dict[str, Any], input_hashes: dict[str, str]) -> dict[str, Any]:
    iteration = args.iteration_dir.resolve()
    target = args.output.resolve() if args.output else iteration / "review_patch.json"
    if target != iteration / "review_patch.json":
        raise AssetError("revision output must be iteration-dir/review_patch.json", path=str(target), code="path_escape")
    if target.exists():
        raise AssetError("review patch already exists", path=str(target), code="output_conflict", exit_code=9)
    _verify_current_inputs(iteration, input_hashes, ["layout.json", "crops.json", "asset_manifest.json", "qa_report.json", "review_report.json", "review_evaluation.json"])
    patch = response["artifacts"]["review_patch"]
    validate_schema("review_patch", patch, args.schema_dir)
    validate_semantics("review_patch", patch)
    if patch["task_id"] != manifest["task_id"] or patch["from_iteration"] != args.iteration:
        raise AssetError("review patch identity mismatch", path="$.artifacts.review_patch", code="iteration_mismatch", exit_code=9)
    expected_hashes = {
        "based_on_review_sha256": sha256_file(iteration / "review_report.json"),
        "based_on_review_evaluation_sha256": sha256_file(iteration / "review_evaluation.json"),
    }
    for key, value in expected_hashes.items():
        if patch[key] != value:
            raise AssetError(f"review patch {key} mismatch", path=f"$.{key}", code="hash_conflict", exit_code=9)
    for key, filename in (("layout_sha256", "layout.json"), ("crops_sha256", "crops.json"), ("asset_manifest_sha256", "asset_manifest.json")):
        if patch["preconditions"][key] != sha256_file(iteration / filename):
            raise AssetError(f"review patch precondition mismatch: {key}", path=f"$.preconditions.{key}", code="hash_conflict", exit_code=9)
    review = load_json(iteration / "review_report.json")
    issue_ids = {item["id"] for item in review["issues"]}
    approved = set(review["approved_elements"])
    if not approved.issubset(set(patch["preserved_elements"])):
        raise AssetError("all approved elements must be preserved", path="$.preserved_elements", code="approved_element")
    for index, operation in enumerate(patch["operations"]):
        if operation["issue_id"] not in issue_ids:
            raise AssetError("patch operation references an unknown issue", path=f"$.operations[{index}].issue_id", code="unknown_issue")
        if operation.get("element_id") in approved and not operation.get("override_reason"):
            raise AssetError("modifying an approved element requires override_reason", path=f"$.operations[{index}]", code="approved_element")
    atomic_write_json(target, patch)
    return {"review_patch": str(target), "sha256": sha256_file(target)}


def _validate_review_references(response: dict[str, Any], layout: dict[str, Any], asset_manifest: dict[str, Any]) -> None:
    element_ids = {item["id"] for item in layout["elements"]}
    asset_ids = {item["id"] for item in asset_manifest["assets"]}
    issue_element_ids: set[str] = set()
    for index, issue in enumerate(response["issues"]):
        unknown_elements = set(issue["element_ids"]) - element_ids - {"slide-root"}
        unknown_assets = set(issue["asset_ids"]) - asset_ids
        if unknown_elements or unknown_assets:
            raise AssetError("review issue references an unknown element or asset", path=f"$.issues[{index}]", code="unknown_reference")
        if issue["severity"] != "suggestion":
            issue_element_ids.update(set(issue["element_ids"]) - {"slide-root"})
        action = issue["recommended_action"]
        if action.get("element_id") and action["element_id"] not in element_ids:
            raise AssetError("recommended action references an unknown element", path=f"$.issues[{index}].recommended_action.element_id", code="unknown_reference")
        if action.get("asset_id") and action["asset_id"] not in asset_ids:
            raise AssetError("recommended action references an unknown asset", path=f"$.issues[{index}].recommended_action.asset_id", code="unknown_reference")
        if action["type"] in {"recrop_asset", "replace_asset"} and not (action.get("asset_id") or issue["asset_ids"]):
            raise AssetError("asset action requires an asset target", path=f"$.issues[{index}].recommended_action", code="missing_target")
        if action["type"] in {"update_element", "update_style", "reclassify_element", "remove_element"} and not (action.get("element_id") or issue["element_ids"]):
            raise AssetError("element action requires an element target", path=f"$.issues[{index}].recommended_action", code="missing_target")
    approved = set(response["approved_elements"])
    if not approved.issubset(element_ids):
        raise AssetError("approved_elements contains an unknown element", path="$.approved_elements", code="unknown_reference")
    if approved & issue_element_ids:
        raise AssetError("approved element also has a non-suggestion issue", path="$.approved_elements", code="approved_element")


def _load_planner_record(path: Path, work_root: Path, schema_dir: Path) -> dict[str, Any]:
    if path.name != "call_record.json":
        raise AssetError("planner-call-record must name call_record.json", path=str(path), code="cli_error", exit_code=2)
    planner_call = path.resolve().parent
    manifest = load_json(planner_call / "call_manifest.json")
    mode = manifest.get("mode")
    if mode not in {"initial", "revision"}:
        raise AssetError("invalid Planner call mode", path=str(planner_call), code="call_bundle")
    _, record, _, _ = load_call_bundle(planner_call, work_root=work_root, role="planner", mode=mode, schema_dir=schema_dir)
    return record


def _finalize_review(args: argparse.Namespace, work_root: Path, call_manifest: dict[str, Any], reviewer_record: dict[str, Any], response: dict[str, Any], input_hashes: dict[str, str]) -> dict[str, Any]:
    if args.planner_call_record is None:
        raise AssetError("review mode requires --planner-call-record", path="--planner-call-record", code="cli_error", exit_code=2)
    iteration = args.iteration_dir.resolve()
    target = args.output.resolve() if args.output else iteration / "review_report.json"
    if target != iteration / "review_report.json":
        raise AssetError("review output must be iteration-dir/review_report.json", path=str(target), code="path_escape")
    if target.exists():
        raise AssetError("review report already exists", path=str(target), code="output_conflict", exit_code=9)
    _verify_current_inputs(iteration, input_hashes, ["layout.json", "qa_report.json", "asset_manifest.json", "rendered_slide.png"])
    request_path = work_root / "request.json"
    request_document = _load_call_input(args.call_dir, "request.json")
    source_path = work_root / request_document["source_image"]
    if not request_path.is_file() or sha256_file(request_path) != input_hashes["request.json"]:
        raise AssetError("request changed after Reviewer call", path=str(request_path), code="hash_conflict", exit_code=9)
    if not source_path.is_file() or sha256_file(source_path) != input_hashes["source.png"]:
        raise AssetError("source changed after Reviewer call", path=str(source_path), code="hash_conflict", exit_code=9)
    layout = load_contract("layout", iteration / "layout.json", args.schema_dir)
    asset_manifest = load_contract("asset_manifest", iteration / "asset_manifest.json", args.schema_dir)
    qa = load_contract("qa_report", iteration / "qa_report.json", args.schema_dir)
    if qa["status"] != "pass":
        raise AssetError("Reviewer cannot run after structural QA failure", path=str(iteration / "qa_report.json"), code="structural_gate", exit_code=8)
    _validate_review_references(response, layout, asset_manifest)
    planner_record = _load_planner_record(args.planner_call_record, work_root, args.schema_dir)
    if planner_record["task_id"] != call_manifest["task_id"]:
        raise AssetError("Planner provenance belongs to another task", path=str(args.planner_call_record), code="call_record")
    if planner_record["context_id"] == reviewer_record["context_id"]:
        raise AssetError(
            "Planner and Reviewer must use different fresh contexts",
            path=str(args.planner_call_record),
            code="context_conflict",
            exit_code=9,
        )

    ordered_issues = []
    for issue in sorted(response["issues"], key=lambda item: item["id"]):
        normalized = dict(issue)
        normalized["element_ids"] = sorted(issue["element_ids"])
        normalized["asset_ids"] = sorted(issue["asset_ids"])
        ordered_issues.append(normalized)
    report = {
        "schema_version": "1.3", "task_id": response["task_id"], "iteration": response["iteration"],
        "reviewer_recommendation": response["reviewer_recommendation"], "scores": response["scores"],
        "issues": ordered_issues,
        "mandatory_visual_checks": response["mandatory_visual_checks"],
        "approved_elements": sorted(response["approved_elements"]), "warnings": sorted(response["warnings"]),
        "review_context": {
            "source_sha256": input_hashes["source.png"], "render_sha256": input_hashes["rendered_slide.png"],
            "layout_sha256": input_hashes["layout.json"], "qa_report_sha256": input_hashes["qa_report.json"],
            "asset_manifest_sha256": input_hashes["asset_manifest.json"], "request_sha256": input_hashes["request.json"],
            "review_rubric_sha256": input_hashes["visual-review-rubric.md"],
            "reviewer_response_schema_sha256": input_hashes["reviewer-response.schema.json"],
            "reviewer_role_version": call_manifest["role_version"],
        },
        "agent_provenance": {
            "planner": provenance_entry(planner_record), "reviewer": provenance_entry(reviewer_record),
            "review_rubric_sha256": input_hashes["visual-review-rubric.md"],
        },
    }
    validate_schema("review_report", report, args.schema_dir)
    validate_semantics("review_report", report)
    atomic_write_json(target, report)
    return {"review_report": str(target), "sha256": sha256_file(target)}


def main() -> int:
    args = parser().parse_args()
    try:
        if args.iteration < 1:
            raise AssetError("iteration must be positive", path="--iteration", code="cli_error", exit_code=2)
        valid = (args.role == "planner" and args.mode in {"initial", "revision"}) or (args.role == "reviewer" and args.mode == "review")
        if not valid:
            raise AssetError("role and mode are incompatible", path="--mode", code="cli_error", exit_code=2)
        work_root = _work_root(args)
        args.call_dir = args.call_dir.resolve()
        manifest, record, response, input_hashes = load_call_bundle(args.call_dir, work_root=work_root, role=args.role, mode=args.mode, schema_dir=args.schema_dir)
        if manifest["iteration"] != args.iteration:
            raise AssetError("call iteration does not match CLI", path="--iteration", code="iteration_mismatch", exit_code=9)
        _validate_identity(response, manifest, args.iteration)
        _verify_work_inputs(args.call_dir, work_root, input_hashes)
        if args.role == "planner" and args.mode == "initial":
            outputs = _finalize_initial(args, manifest, response)
        elif args.role == "planner":
            outputs = _finalize_revision(args, manifest, response, input_hashes)
        else:
            outputs = _finalize_review(args, work_root, manifest, record, response, input_hashes)
        log_event(args.log_file, level="info", component=COMPONENT, event="completed", message="Agent response finalized", run_id=args.run_id, iteration=args.iteration, data={"role": args.role, "mode": args.mode})
        return success(COMPONENT, outputs, run_id=args.run_id, iteration=args.iteration)
    except (ContractError, UnicodeError, json.JSONDecodeError) as exc:
        wrapped = AssetError(str(exc), path="$", code="contract_error")
        log_event(args.log_file, level="error", component=COMPONENT, event="failed", message=str(wrapped), run_id=args.run_id, iteration=args.iteration, data={"exit_code": 4})
        return failure(COMPONENT, wrapped, run_id=args.run_id, iteration=args.iteration)
    except Exception as exc:
        log_event(args.log_file, level="error", component=COMPONENT, event="failed", message=str(exc), run_id=args.run_id, iteration=args.iteration, data={"exit_code": getattr(exc, "exit_code", 70)})
        return failure(COMPONENT, exc, run_id=args.run_id, iteration=args.iteration)


if __name__ == "__main__":
    raise SystemExit(main())
