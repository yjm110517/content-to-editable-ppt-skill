from __future__ import annotations

import argparse
from pathlib import Path

from asset_common import failure, success
from revision_context import load_revision_context, validate_revision


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Canonical Revision through all gates without publishing files.")
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--current-dir", type=Path, required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--schema-dir", type=Path, default=Path(__file__).resolve().parents[1] / "schemas")
    args = parser.parse_args()
    try:
        ctx = load_revision_context(args.work_root, args.current_dir, args.schema_dir)
        patch = ctx.document(args.patch, "revision_patch")
        validate_revision(ctx, patch, ctx.digest(args.patch))
        return success("validate_revision_patch", {"valid": True}, run_id="local", iteration=None)
    except Exception as exc:
        return failure("validate_revision_patch", exc, run_id="local", iteration=None)


if __name__ == "__main__":
    raise SystemExit(main())
