from __future__ import annotations

import argparse
import json
from pathlib import Path

from schema_utils import ContractError, load_json
from wireframe_rules import apply_correction


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a bounded P2 Wireframe Contract Correction")
    parser.add_argument("--spec-dir", type=Path, required=True)
    parser.add_argument("--validation-report", type=Path, required=True)
    parser.add_argument("--correction", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        specs = [load_json(path) for path in sorted(args.spec_dir.resolve().glob("*.json"))]
        updated = apply_correction(specs=specs, report=load_json(args.validation_report.resolve()), correction=load_json(args.correction.resolve()))
        output = args.output_dir.resolve()
        if output.exists() and any(output.iterdir()):
            raise ContractError([{"path": "--output-dir", "code": "overwrite_forbidden", "message": "Correction output directory must be empty"}])
        output.mkdir(parents=True, exist_ok=True)
        for spec in updated:
            path = output / f"{spec['slide_id']}-r{spec['revision']:03d}.json"
            path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "ok", "slides": len(updated)}, ensure_ascii=False))
        return 0
    except ContractError as exc:
        print(json.dumps({"status": "error", "errors": exc.errors}, ensure_ascii=False))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
