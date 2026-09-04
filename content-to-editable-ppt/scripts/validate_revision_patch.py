from __future__ import annotations

import argparse
from pathlib import Path

from asset_common import load_contract, sha256_file
from revision_patch import validate_patch


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Canonical Reconstruction Plan revision without publishing it.")
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--current-dir", type=Path, required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--schema-dir", type=Path, default=Path(__file__).resolve().parents[1] / "schemas")
    args = parser.parse_args()
    work, current = args.work_root.resolve(), args.current_dir.resolve()
    request = load_contract("request", work / "request.json", args.schema_dir)
    base = load_contract("reconstruction_plan", current / "reconstruction-plan.json", args.schema_dir)
    patch = load_contract("revision_patch", args.patch.resolve(), args.schema_dir)
    handoff = load_contract("reconstruction_handoff", work / "reconstruction-handoff.json", args.schema_dir)
    review = load_contract("review_report", current / "review_report.json", args.schema_dir)
    evaluation = load_contract("review_evaluation", current / "review_evaluation.json", args.schema_dir)
    validate_patch(patch, base, handoff, review, evaluation, task_id=request["task_id"], base_sha256=sha256_file(current / "reconstruction-plan.json"), review_sha256=sha256_file(current / "review_report.json"), evaluation_sha256=sha256_file(current / "review_evaluation.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
