from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from asset_common import (
    AssetError,
    atomic_write_bytes,
    atomic_write_json,
    failure,
    resolve_under,
    sha256_file,
    success,
)
from schema_utils import (
    ContractError,
    is_safe_relative_path,
    load_json,
    validate_schema,
    validate_semantics,
)
from visual_first_handoff import project_slide, validate_cross_stage


COMPONENT = "materialize_reconstruction_handoff"
FIXED_OUTPUTS = {
    "source_content": "source-content.json",
    "wireframe": "wireframe.md",
    "visual_spec": "visual-spec.json",
    "reconstruction_handoff": "reconstruction-handoff.json",
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Materialize one validated Stage 1 / Stage 2 handoff for reconstruction.")
    result.add_argument("--stage1-authority", required=True, type=Path)
    result.add_argument("--stage2-handoff", required=True, type=Path)
    result.add_argument("--slide-id", required=True)
    result.add_argument("--work-root", required=True, type=Path)
    result.add_argument("--schema-dir", type=Path, default=Path(__file__).resolve().parents[1] / "schemas")
    result.add_argument("--force", action="store_true")
    return result


def _contract_asset_error(exc: ContractError) -> AssetError:
    detail = exc.errors[0] if exc.errors else {"path": "$", "code": "contract_error", "message": str(exc)}
    return AssetError(detail["message"], path=detail["path"], code=detail["code"])


def _load_contract(kind: str, path: Path, schema_dir: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AssetError("input file does not exist", path=str(path), code="missing_input", exit_code=3)
    try:
        document = load_json(path)
        validate_schema(kind, document, schema_dir)
        validate_semantics(kind, document)
        return document
    except json.JSONDecodeError as exc:
        raise AssetError(str(exc), path=str(path), code="invalid_json") from exc
    except ContractError as exc:
        raise _contract_asset_error(exc) from exc


def _verified_file(root: Path, reference: dict[str, str], *, changed_code: str, label: str) -> tuple[Path, bytes]:
    path = resolve_under(root, reference["path"])
    if not path.is_file():
        raise AssetError(f"{label} is missing", path=reference["path"], code=changed_code, exit_code=3)
    content = path.read_bytes()
    if sha256_file(path) != reference["sha256"]:
        raise AssetError(f"{label} raw SHA-256 does not match the approved handoff", path=reference["path"], code=changed_code)
    return path, content


def _validate_visual_spec(path: Path, content: bytes, reference_path: str) -> dict[str, Any]:
    if not reference_path.lower().endswith(".json"):
        raise AssetError("visual spec must use a .json file", path=reference_path, code="invalid_visual_spec")
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssetError("visual spec must be valid UTF-8 JSON", path=reference_path, code="invalid_visual_spec") from exc
    if not isinstance(value, dict):
        raise AssetError("visual spec must be a JSON object", path=reference_path, code="invalid_visual_spec")
    return value


def _collect_evidence(
    stage1_path: Path,
    stage1: dict[str, Any],
    stage2_path: Path,
    stage2: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    stage1_by_id = {slide["slide_id"]: slide for slide in stage1["slides"]}
    stage2_by_id = {slide["slide_id"]: slide for slide in stage2["slides"]}
    evidence: dict[str, dict[str, Any]] = {}
    for slide_id in sorted(set(stage1_by_id) & set(stage2_by_id)):
        stage1_slide = stage1_by_id[slide_id]
        stage2_slide = stage2_by_id[slide_id]
        wireframe_path, wireframe_bytes = _verified_file(
            stage1_path.parent,
            stage1_slide["wireframe"],
            changed_code="wireframe_changed",
            label="wireframe",
        )
        approved_design_path, approved_design_bytes = _verified_file(
            stage2_path.parent,
            stage2_slide["approved_design"],
            changed_code="approved_design_changed",
            label="approved design",
        )
        visual_spec_ref = stage2_slide["visual_spec"]
        visual_spec_path = resolve_under(stage2_path.parent, visual_spec_ref["path"])
        if not visual_spec_path.is_file():
            raise AssetError("visual spec is missing", path=visual_spec_ref["path"], code="visual_spec_changed", exit_code=3)
        visual_spec_bytes = visual_spec_path.read_bytes()
        _validate_visual_spec(visual_spec_path, visual_spec_bytes, visual_spec_ref["path"])
        if sha256_file(visual_spec_path) != visual_spec_ref["sha256"]:
            raise AssetError("visual spec raw SHA-256 does not match the approved handoff", path=visual_spec_ref["path"], code="visual_spec_changed")
        evidence[slide_id] = {
            "wireframe_path": wireframe_path,
            "wireframe_bytes": wireframe_bytes,
            "approved_design_path": approved_design_path,
            "approved_design_bytes": approved_design_bytes,
            "visual_spec_path": visual_spec_path,
            "visual_spec_bytes": visual_spec_bytes,
        }
    return evidence


def _validate_output_destinations(paths: list[Path], work_root: Path, *, force: bool) -> None:
    for path in paths:
        if path.exists() and not path.is_file():
            raise AssetError("materialized output path is not a file", path=str(path), code="output_collision", exit_code=9)
        parent = path.parent
        while parent != work_root.parent:
            if parent.exists() and not parent.is_dir():
                raise AssetError("materialized output parent is not a directory", path=str(parent), code="output_collision", exit_code=9)
            if parent == work_root:
                break
            parent = parent.parent
    collisions = [path for path in paths if path.exists()]
    if collisions and not force:
        raise AssetError("materialized output already exists", path=str(collisions[0]), code="output_collision", exit_code=9)


def materialize_handoff(args: argparse.Namespace) -> dict[str, str]:
    work_root = args.work_root.resolve()
    if not work_root.is_dir():
        raise AssetError("work root does not exist", path=str(work_root), code="missing_input", exit_code=3)

    stage1_path = args.stage1_authority.resolve()
    stage2_path = args.stage2_handoff.resolve()
    stage1 = _load_contract("stage1_authority", stage1_path, args.schema_dir)
    stage2 = _load_contract("stage2_handoff", stage2_path, args.schema_dir)
    request_path = work_root / "request.json"
    request = _load_contract("request", request_path, args.schema_dir)

    source_image = request["source_image"]
    if not is_safe_relative_path(source_image):
        raise AssetError("request.source_image must be a safe work-root-relative path", path="$.source_image", code="unsafe_path")
    source_target = resolve_under(work_root, source_image)

    stage1_sha256 = sha256_file(stage1_path)
    stage2_sha256 = sha256_file(stage2_path)
    evidence = _collect_evidence(stage1_path, stage1, stage2_path, stage2)
    try:
        validate_cross_stage(stage1, stage2, stage1_sha256)
    except ContractError as exc:
        raise _contract_asset_error(exc) from exc
    if args.slide_id not in evidence:
        raise AssetError(f"unknown slide_id: {args.slide_id}", path="$.slide_id", code="unknown_slide")

    stage1_slide = next(slide for slide in stage1["slides"] if slide["slide_id"] == args.slide_id)
    stage2_slide = next(slide for slide in stage2["slides"] if slide["slide_id"] == args.slide_id)
    current_evidence = evidence[args.slide_id]
    provenance = {
        "stage1_authority_sha256": stage1_sha256,
        "stage2_handoff_sha256": stage2_sha256,
        "approved_design_sha256": stage2_slide["approved_design"]["sha256"],
        "wireframe_sha256": stage1_slide["wireframe"]["sha256"],
        "visual_spec_sha256": stage2_slide["visual_spec"]["sha256"],
    }
    projection = project_slide(
        stage1,
        stage2,
        slide_id=args.slide_id,
        source_image=source_image,
        provenance=provenance,
    )
    try:
        validate_schema("reconstruction_handoff", projection["reconstruction_handoff"], args.schema_dir)
        validate_semantics("reconstruction_handoff", projection["reconstruction_handoff"])
    except ContractError as exc:
        raise _contract_asset_error(exc) from exc

    output_paths = {
        name: work_root / filename
        for name, filename in FIXED_OUTPUTS.items()
    }
    output_paths["approved_design"] = source_target
    generated_paths = list(output_paths.values())
    if len({path.resolve() for path in generated_paths}) != len(generated_paths) or source_target == request_path.resolve():
        raise AssetError("request.source_image conflicts with a materialized contract output", path="$.source_image", code="output_collision", exit_code=9)
    _validate_output_destinations(generated_paths, work_root, force=args.force)

    atomic_write_json(output_paths["source_content"], projection["source_content"])
    atomic_write_bytes(output_paths["approved_design"], current_evidence["approved_design_bytes"])
    atomic_write_bytes(output_paths["wireframe"], current_evidence["wireframe_bytes"])
    atomic_write_bytes(output_paths["visual_spec"], current_evidence["visual_spec_bytes"])
    atomic_write_json(output_paths["reconstruction_handoff"], projection["reconstruction_handoff"])
    return {name: str(path.resolve()) for name, path in output_paths.items()}


def main() -> int:
    args = parser().parse_args()
    try:
        outputs = materialize_handoff(args)
        return success(COMPONENT, outputs, run_id="local", iteration=None)
    except Exception as exc:
        return failure(COMPONENT, exc, run_id="local", iteration=None)


if __name__ == "__main__":
    raise SystemExit(main())
