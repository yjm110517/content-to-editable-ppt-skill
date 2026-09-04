from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from asset_common import AssetError, atomic_write_json, failure, load_contract, sha256_file, success
from compile_reconstruction_plan import read_source_metadata
from reconstruction_plan import compile_reconstruction_plan
from revision_patch import apply_patch, validate_patch
from schema_utils import ContractError, load_json, validate_schema, validate_semantics
from shared_validator import validate_documents
from visual_first_planner import content_authority_from_handoff, validate_plan_against_handoff


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Atomically apply a scoped Canonical Reconstruction Plan revision.")
    result.add_argument("--work-root", type=Path, required=True)
    result.add_argument("--current-dir", type=Path, required=True)
    result.add_argument("--patch", type=Path, required=True)
    result.add_argument("--next-dir", type=Path, required=True)
    result.add_argument("--schema-dir", type=Path, default=Path(__file__).resolve().parents[1] / "schemas")
    return result


def apply_revision(args: argparse.Namespace) -> dict[str, str]:
    work = args.work_root.resolve()
    current, next_dir, patch_path = args.current_dir.resolve(), args.next_dir.resolve(), args.patch.resolve()
    expected_current = work / "iterations" / current.name
    expected_next = work / "iterations" / f"{int(current.name) + 1:02d}" if current.name.isdigit() else None
    if current != expected_current or not current.is_dir() or expected_next is None or next_dir != expected_next or next_dir.exists():
        raise AssetError("revision directories must be consecutive work-root iterations and next must be absent", code="iteration_boundary", exit_code=9)
    for path in (patch_path, work / "request.json", work / "reconstruction-handoff.json", work / "source.png", current / "reconstruction-plan.json", current / "review_report.json", current / "review_evaluation.json"):
        try:
            path.relative_to(work)
        except ValueError as exc:
            raise AssetError("revision input escapes work root", path=str(path), code="path_escape") from exc
    request = load_contract("request", work / "request.json", args.schema_dir)
    handoff = load_contract("reconstruction_handoff", work / "reconstruction-handoff.json", args.schema_dir)
    base = load_contract("reconstruction_plan", current / "reconstruction-plan.json", args.schema_dir)
    patch = load_contract("revision_patch", patch_path, args.schema_dir)
    review = load_contract("review_report", current / "review_report.json", args.schema_dir)
    evaluation = load_contract("review_evaluation", current / "review_evaluation.json", args.schema_dir)
    validate_patch(patch, base, handoff, review, evaluation, task_id=request["task_id"], base_sha256=sha256_file(current / "reconstruction-plan.json"), review_sha256=sha256_file(current / "review_report.json"), evaluation_sha256=sha256_file(current / "review_evaluation.json"))
    if sha256_file(work / request["source_image"]) != handoff["provenance"]["approved_design_sha256"]:
        raise AssetError("Approved Design changed after materialization", code="hash_conflict", exit_code=9)
    plan, diff = apply_patch(base, patch, handoff_sha256=sha256_file(work / "reconstruction-handoff.json"), approved_design_sha256=sha256_file(work / request["source_image"]), patch_sha256=sha256_file(patch_path))
    try:
        validate_schema("reconstruction_plan", plan, args.schema_dir)
        validate_semantics("reconstruction_plan", plan)
        validate_plan_against_handoff(plan, handoff, request, iteration=patch["to_iteration"], slide_id=patch["page_id"])
        artifacts = compile_reconstruction_plan(plan, content_authority_from_handoff(handoff), request, read_source_metadata(work / request["source_image"]), handoff["structured_data"])
        validate_documents(artifacts, {}, profile="candidate", schema_dir=args.schema_dir)
    except ContractError as exc:
        raise AssetError(str(exc), code="revision_validation") from exc
    stage = Path(__import__("tempfile").mkdtemp(prefix=f".{next_dir.name}-revision-", dir=current.parent))
    try:
        atomic_write_json(stage / "reconstruction-plan.json", plan)
        atomic_write_json(stage / "revision_patch.json", patch)
        atomic_write_json(stage / "plan-diff.json", diff)
        for key, filename in (("layout", "layout.json"), ("crops", "crops.json"), ("asset_manifest", "asset_manifest.json")):
            atomic_write_json(stage / filename, artifacts[key])
        if sha256_file(current / "reconstruction-plan.json") != patch["base_plan_sha256"]:
            raise AssetError("baseline changed while revision was applied", code="hash_conflict", exit_code=9)
        os.replace(stage, next_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {"next_iteration": str(next_dir), "reconstruction_plan": str(next_dir / "reconstruction-plan.json"), "plan_diff": str(next_dir / "plan-diff.json")}


def main() -> int:
    args = parser().parse_args()
    try:
        return success("apply_revision_patch", apply_revision(args), run_id="local", iteration=None)
    except Exception as exc:
        return failure("apply_revision_patch", exc, run_id="local", iteration=None)


if __name__ == "__main__":
    raise SystemExit(main())
