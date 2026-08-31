from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

from PIL import Image

from asset_common import AssetError, atomic_write_json, failure, load_contract, resolve_under, success
from reconstruction_plan import compile_reconstruction_plan
from schema_utils import ContractError, load_json, validate_schema, validate_semantics
from shared_validator import validate_documents


COMPONENT = "compile_reconstruction_plan"
OUTPUT_NAMES = ("layout.json", "crops.json", "asset_manifest.json")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Compile a Canonical Reconstruction Plan into legacy single-slide runtime artifacts.")
    result.add_argument("--plan", required=True, type=Path)
    result.add_argument("--content", required=True, type=Path)
    result.add_argument("--iteration-dir", required=True, type=Path)
    result.add_argument("--schema-dir", type=Path, default=Path(__file__).resolve().parents[1] / "schemas")
    result.add_argument("--force", action="store_true")
    return result


def _contract_asset_error(exc: ContractError) -> AssetError:
    detail = exc.errors[0] if exc.errors else {"path": "$", "code": "contract_error", "message": str(exc)}
    return AssetError(detail["message"], path=detail["path"], code=detail["code"])


def _source_size(path: Path) -> dict[str, int]:
    previous_limit = Image.MAX_IMAGE_PIXELS
    try:
        Image.MAX_IMAGE_PIXELS = 100_000_000
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as image:
                width, height = image.size
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise AssetError("approved design exceeds safe pixel limit", path=str(path), code="image_too_large") from exc
    except OSError as exc:
        raise AssetError("approved design is unreadable", path=str(path), code="unreadable_image", exit_code=3) from exc
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit
    return {"width_px": width, "height_px": height}


def _load_reconstruction_plan(path: Path, schema_dir: Path) -> dict:
    if not path.is_file():
        raise AssetError("input file does not exist", path=str(path), code="missing_input", exit_code=3)
    try:
        document = load_json(path)
        validate_schema("reconstruction_plan", document, schema_dir)
        validate_semantics("reconstruction_plan", document)
        return document
    except (json.JSONDecodeError, ContractError) as exc:
        if isinstance(exc, ContractError):
            raise _contract_asset_error(exc) from exc
        raise AssetError(str(exc), path=str(path), code="invalid_json") from exc


def compile_to_iteration(args: argparse.Namespace) -> dict[str, str]:
    iteration_dir = args.iteration_dir.resolve()
    if not iteration_dir.is_dir():
        raise AssetError("iteration directory does not exist", path=str(iteration_dir), code="missing_input", exit_code=3)
    if iteration_dir.parent.name != "iterations" or not iteration_dir.name.isdigit():
        raise AssetError("iteration directory must be work-root/iterations/NN", path=str(iteration_dir), code="iteration_boundary")
    iteration = int(iteration_dir.name)
    if iteration < 1:
        raise AssetError("iteration must be positive", path=str(iteration_dir), code="iteration_boundary")
    work_root = iteration_dir.parent.parent.resolve()

    request_path = work_root / "request.json"
    expected_content = work_root / "source-content.json"
    if args.content.resolve() != expected_content:
        raise AssetError("content authority must be work-root/source-content.json", path=str(args.content), code="path_escape")
    if not expected_content.is_file():
        raise AssetError("content authority does not exist", path=str(expected_content), code="missing_input", exit_code=3)
    plan_path = args.plan.resolve()
    try:
        plan_path.relative_to(work_root)
    except ValueError as exc:
        raise AssetError("plan must remain inside work root", path=str(plan_path), code="path_escape") from exc

    request = load_contract("request", request_path, args.schema_dir)
    plan = _load_reconstruction_plan(plan_path, args.schema_dir)
    if plan["page"]["iteration"] != iteration:
        raise AssetError("plan iteration does not match iteration directory", path="$.page.iteration", code="iteration_mismatch")
    content = load_json(expected_content)

    source_ref = plan["source"]["approved_design"]
    source = resolve_under(work_root, source_ref)
    request_source = resolve_under(work_root, request["source_image"])
    if source != request_source:
        raise AssetError("approved design must match request source_image", path="$.source.approved_design", code="source_mismatch")
    if not source.is_file():
        raise AssetError("approved design does not exist", path=str(source), code="missing_input", exit_code=3)

    try:
        artifacts = compile_reconstruction_plan(plan, content, request, _source_size(source))
        paths = {kind: iteration_dir / name for kind, name in zip(("layout", "crops", "asset_manifest"), OUTPUT_NAMES)}
        validate_documents(artifacts, paths, profile="candidate", schema_dir=args.schema_dir)
    except ContractError as exc:
        raise _contract_asset_error(exc) from exc

    collisions = [path for path in paths.values() if path.exists()]
    if collisions and not args.force:
        raise AssetError("compiled output already exists", path=str(collisions[0]), code="output_collision", exit_code=9)

    for kind in ("layout", "crops", "asset_manifest"):
        atomic_write_json(paths[kind], artifacts[kind])
    return {kind: str(path.resolve()) for kind, path in paths.items()}


def main() -> int:
    args = parser().parse_args()
    iteration = int(args.iteration_dir.name) if args.iteration_dir.name.isdigit() else None
    try:
        outputs = compile_to_iteration(args)
        return success(COMPONENT, outputs, run_id="local", iteration=iteration)
    except (json.JSONDecodeError, ContractError) as exc:
        wrapped = _contract_asset_error(exc) if isinstance(exc, ContractError) else AssetError(str(exc), code="invalid_json")
        return failure(COMPONENT, wrapped, run_id="local", iteration=iteration)
    except Exception as exc:
        return failure(COMPONENT, exc, run_id="local", iteration=iteration)


if __name__ == "__main__":
    raise SystemExit(main())
