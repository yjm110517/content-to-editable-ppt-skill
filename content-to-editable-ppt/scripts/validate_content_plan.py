from __future__ import annotations

import argparse
import json
from pathlib import Path

from content_plan_rules import validate_candidate_outline, validate_material_understanding, validate_outline_confirmation, validate_task_route
from schema_utils import ContractError, load_json, validate_schema


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate a P1 content planning artifact")
    result.add_argument("--profile", choices=("route", "deck-request", "materials", "candidate", "confirmation", "approved-outline"), required=True)
    result.add_argument("--input", type=Path, required=True)
    result.add_argument("--schema-dir", type=Path, default=Path(__file__).resolve().parents[1] / "schemas")
    result.add_argument("--deck-request", type=Path)
    result.add_argument("--materials", type=Path)
    result.add_argument("--candidate", type=Path)
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
        elif args.profile == "deck-request":
            validate_schema("deck_request", document, args.schema_dir.resolve())
            details = {}
        elif args.profile == "candidate":
            if not args.deck_request or not args.materials:
                raise ContractError([{"path": "$", "code": "missing_input", "message": "candidate validation requires --deck-request and --materials"}])
            validate_candidate_outline(document, deck_request=load_json(args.deck_request), materials=load_json(args.materials), schema_dir=args.schema_dir.resolve())
            details = {"page_count": len(document["pages"])}
        elif args.profile == "confirmation":
            if not args.candidate:
                raise ContractError([{"path": "$", "code": "missing_input", "message": "confirmation validation requires --candidate"}])
            validate_outline_confirmation(load_json(args.candidate), document, args.schema_dir.resolve())
            details = {"confirmation_status": document["status"]}
        else:
            validate_schema("approved_outline", document, args.schema_dir.resolve())
            details = {"page_count": len(document["pages"])}
        print(json.dumps({"status": "ok", "profile": args.profile, **details}, ensure_ascii=False))
        return 0
    except ContractError as exc:
        print(json.dumps({"status": "error", "errors": exc.errors}, ensure_ascii=False))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
