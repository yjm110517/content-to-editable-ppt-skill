from __future__ import annotations

import argparse
import json
from pathlib import Path

from content_plan_rules import validate_material_understanding, validate_task_route
from schema_utils import ContractError, load_json, validate_schema


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate a P1 content planning artifact")
    result.add_argument("--profile", choices=("route", "deck-request", "materials"), required=True)
    result.add_argument("--input", type=Path, required=True)
    result.add_argument("--schema-dir", type=Path, default=Path(__file__).resolve().parents[1] / "schemas")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        document = load_json(args.input.resolve())
        if args.profile == "route":
            validate_task_route(document, args.schema_dir.resolve())
            details = {"route": document["route"]}
        elif args.profile == "materials":
            details = validate_material_understanding(document, args.schema_dir.resolve())
        else:
            validate_schema("deck_request", document, args.schema_dir.resolve())
            details = {}
        print(json.dumps({"status": "ok", "profile": args.profile, **details}, ensure_ascii=False))
        return 0
    except ContractError as exc:
        print(json.dumps({"status": "error", "errors": exc.errors}, ensure_ascii=False))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
