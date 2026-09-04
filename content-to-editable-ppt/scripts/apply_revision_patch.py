from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path

from agent_common import ensure_under
from asset_common import atomic_write_bytes, atomic_write_json, failure, success
from revision_context import load_revision_context, require, validate_revision


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Atomically apply a scoped Canonical Reconstruction Plan revision.")
    result.add_argument("--work-root", type=Path, required=True)
    result.add_argument("--current-dir", type=Path, required=True)
    result.add_argument("--patch", type=Path, required=True)
    result.add_argument("--next-dir", type=Path, required=True)
    result.add_argument("--schema-dir", type=Path, default=Path(__file__).resolve().parents[1] / "schemas")
    return result


def apply_revision(args: argparse.Namespace) -> dict[str, str]:
    ctx = load_revision_context(args.work_root, args.current_dir, args.schema_dir)
    next_dir = ensure_under(args.next_dir, ctx.work)
    require(next_dir == ctx.current.parent / f"{int(ctx.current.name) + 1:02d}" and not next_dir.exists(),
            "next directory must be absent and consecutive", "iteration_boundary")
    patch_path = ensure_under(args.patch, ctx.work)
    patch = ctx.document(patch_path, "revision_patch")
    plan, diff, artifacts = validate_revision(ctx, patch, ctx.digest(patch_path))
    stage = Path(tempfile.mkdtemp(prefix=f".{next_dir.name}-revision-", dir=ctx.current.parent))
    try:
        atomic_write_json(stage / "reconstruction-plan.json", plan)
        atomic_write_bytes(stage / "revision_patch.json", ctx.read(patch_path))
        atomic_write_json(stage / "plan-diff.json", diff)
        for key, filename in (("layout", "layout.json"), ("crops", "crops.json"), ("asset_manifest", "asset_manifest.json")):
            atomic_write_json(stage / filename, artifacts[key])
        ctx.verify_unchanged()
        ensure_under(next_dir, ctx.work)
        require(not next_dir.exists(), "next iteration appeared during apply", "output_conflict")
        # Windows rename refuses existing destinations, including empty directories.
        os.rename(stage, next_dir)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {"next_iteration": str(next_dir), "reconstruction_plan": str(next_dir / "reconstruction-plan.json"), "plan_diff": str(next_dir / "plan-diff.json")}


def main() -> int:
    args = parser().parse_args()
    try:
        return success("apply_revision_patch", apply_revision(args), run_id="local", iteration=None)
    except Exception as exc:
        return failure("apply_revision_patch", exc, run_id="local", iteration=None)


if __name__ == "__main__":
    raise SystemExit(main())
