from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from schema_utils import ContractError, SCHEMA_FILES, load_json, load_yaml
from shared_validator import validate_documents


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate Content to Editable PPT contracts through the shared validation framework.")
    result.add_argument("--schema-dir", type=Path, default=Path(__file__).resolve().parents[1] / "schemas")
    result.add_argument("--phase", choices=("preflight", "build-ready"), default="preflight")
    for kind in SCHEMA_FILES:
        result.add_argument("--" + kind.replace("_", "-"), dest=kind, type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    selected = {kind: getattr(args, kind) for kind in SCHEMA_FILES if getattr(args, kind) is not None}
    if not selected:
        parser().error("at least one contract path is required")
    try:
        documents = {}
        for kind, path in selected.items():
            if not path.is_file():
                raise FileNotFoundError(path)
            document = load_yaml(path) if kind == "agent_role" else load_json(path)
            documents[kind] = document
        profile = "pre_build" if args.phase == "build-ready" else "candidate"
        validate_documents(documents, selected, profile=profile, schema_dir=args.schema_dir)
        print(json.dumps({"status": "ok", "component": "validate_spec", "phase": args.phase, "validated": sorted(documents), "error": None}, ensure_ascii=False))
        return 0
    except FileNotFoundError as exc:
        print(json.dumps({"status": "error", "component": "validate_spec", "error": {"exit_code": 3, "category": "input", "message": f"missing file: {exc}"}}, ensure_ascii=False))
        return 3
    except (json.JSONDecodeError, yaml.YAMLError, ContractError) as exc:
        errors = exc.errors if isinstance(exc, ContractError) else [{"path": "$", "code": "invalid_json", "message": str(exc)}]
        print(json.dumps({"status": "error", "component": "validate_spec", "error": {"exit_code": 4, "category": "contract", "message": "contract validation failed", "details": errors}}, ensure_ascii=False))
        return 4
    except Exception as exc:
        print(json.dumps({"status": "error", "component": "validate_spec", "error": {"exit_code": 70, "category": "internal", "message": str(exc)}}, ensure_ascii=False))
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
