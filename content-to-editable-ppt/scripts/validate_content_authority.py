from __future__ import annotations

import argparse
import json
from pathlib import Path

from asset_common import AssetError, atomic_write_json, failure, load_contract, sha256_file, success
from schema_utils import ContractError, validate_schema
from text_identity import build_compatibility_map, compare_authority, compatibility_view, layout_with_ppt_text, load_json


COMPONENT = "validate_content_authority"
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Compare canonical authority text with text extracted from the editable PPTX.")
    result.add_argument("--authority", type=Path, required=True)
    result.add_argument("--layout", type=Path, required=True)
    result.add_argument("--ppt", type=Path, required=True)
    result.add_argument("--compatibility-map", type=Path)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--schema-dir", type=Path, default=SCHEMA_DIR)
    result.add_argument("--run-id", default="content-authority")
    return result


def validate(args: argparse.Namespace) -> dict:
    authority = load_json(args.authority)
    layout = load_contract("layout", args.layout, args.schema_dir)
    if layout["schema_version"] == "1.3":
        if args.compatibility_map:
            mapping = load_contract("text_identity_map", args.compatibility_map, args.schema_dir)
        else:
            mapping = build_compatibility_map(layout, authority)
        layout = compatibility_view(layout, mapping, strict=False)
    extracted_layout = layout_with_ppt_text(layout, args.ppt)
    comparison = compare_authority(authority, extracted_layout)
    report = {
        "schema_version": "1.0",
        "authority_sha256": sha256_file(args.authority),
        "layout_sha256": sha256_file(args.layout),
        "ppt_sha256": sha256_file(args.ppt),
        **comparison,
    }
    validate_schema("content_authority_report", report, args.schema_dir)
    atomic_write_json(args.output, report)
    return report


def main() -> int:
    args = parser().parse_args()
    try:
        if args.output.exists():
            raise AssetError("content authority report already exists", path=str(args.output), code="output_collision", exit_code=9)
        report = validate(args)
        if report["status"] != "pass":
            print(json.dumps({"status": "error", "component": COMPONENT, "run_id": args.run_id, "outputs": {"report": str(args.output.resolve())}, "error": {"exit_code": 8, "category": "content_failure", "message": "canonical content does not match editable PPT text"}}, ensure_ascii=False, sort_keys=True))
            return 8
        return success(COMPONENT, {"report": str(args.output.resolve()), "status": "pass"}, run_id=args.run_id, iteration=None)
    except (ContractError, json.JSONDecodeError) as exc:
        return failure(COMPONENT, AssetError(str(exc), code="contract_error"), run_id=args.run_id, iteration=None)
    except Exception as exc:
        return failure(COMPONENT, exc, run_id=args.run_id, iteration=None)


if __name__ == "__main__":
    raise SystemExit(main())
