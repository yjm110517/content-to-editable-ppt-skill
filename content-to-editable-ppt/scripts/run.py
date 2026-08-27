from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from asset_common import AssetError, log_event
from contact_sheets import compose_preview_sheet
from deck_build_request import DIMENSIONS, load_request, stage_assets
from deck_roundtrip import run_roundtrip
from schema_utils import ContractError, error
from verify_deck import verify


COMPONENT = "run"
SCRIPT_DIR = Path(__file__).resolve().parent


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Build, render, verify, and atomically deliver a confirmed editable multi-page PowerPoint deck.")
    result.add_argument("--request", type=Path, required=True)
    result.add_argument("--work-dir", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--asset-root", type=Path)
    result.add_argument("--node", type=Path)
    result.add_argument("--timeout-seconds", type=int, default=240)
    return result


def _contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_roots(work_dir: Path, output_dir: Path, asset_root: Path | None) -> tuple[Path, Path, Path | None]:
    work = work_dir.resolve(); output = output_dir.resolve(); asset = asset_root.resolve() if asset_root is not None else None
    if work.exists(): raise AssetError("work-dir must not exist", path=str(work), code="output_collision", exit_code=9)
    if output.exists(): raise AssetError("output-dir must not exist", path=str(output), code="output_collision", exit_code=9)
    roots = [("work-dir", work), ("output-dir", output)] + ([] if asset is None else [("asset-root", asset)])
    for left_index, (left_name, left) in enumerate(roots):
        for right_name, right in roots[left_index + 1:]:
            if _contains(left, right) or _contains(right, left):
                raise AssetError(f"{left_name} and {right_name} must not contain each other", code="path_overlap", exit_code=2)
    return work, output, asset


def _subprocess(command: list[str], *, timeout: int, component: str, exit_code: int, log: Path) -> dict[str, Any]:
    log_event(log, level="info", component=COMPONENT, event=f"{component}_started", message=f"Starting {component}", run_id="direct-deck", iteration=None, data={})
    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as exc:
        raise AssetError(f"{component} timed out", code=f"{component}_timeout", exit_code=exit_code) from exc
    if completed.returncode:
        message = completed.stdout.strip() or completed.stderr.strip() or f"{component} failed"
        raise AssetError(message, code=f"{component}_failed", exit_code=completed.returncode if completed.returncode in {2, 3, 4, 5, 6, 7, 8, 9, 70} else exit_code)
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssetError(f"{component} returned invalid JSON", code="invalid_subprocess_result", exit_code=70) from exc
    # Existing environment_preflight reports its successful state as "ready";
    # all direct build stages report "ok".
    if result.get("status") not in {"ok", "ready"}:
        raise AssetError(f"{component} did not return success", code=f"{component}_failed", exit_code=exit_code)
    log_event(log, level="info", component=COMPONENT, event=f"{component}_completed", message=f"Completed {component}", run_id="direct-deck", iteration=None, data={})
    return result


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _publish(*, output_dir: Path, output_name: str, pptx: Path, preview: Path) -> tuple[Path, Path]:
    parent = output_dir.parent; parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=parent))
    try:
        final_pptx = stage / f"{output_name}_editable.pptx"; final_preview = stage / f"{output_name}_preview.png"
        shutil.copy2(pptx, final_pptx); shutil.copy2(preview, final_preview)
        if {item.name for item in stage.iterdir()} != {final_pptx.name, final_preview.name}:
            raise AssetError("delivery stage contains unexpected files", code="delivery_contamination", exit_code=9)
        # os.replace could overwrite a concurrently-created delivery.  A plain
        # directory rename keeps the public no-overwrite contract intact.
        if output_dir.exists():
            raise AssetError("output-dir was created during this run", path=str(output_dir), code="output_collision", exit_code=9)
        os.rename(stage, output_dir)
        return output_dir / final_pptx.name, output_dir / final_preview.name
    finally:
        if stage.exists(): shutil.rmtree(stage, ignore_errors=True)


def execute(args: argparse.Namespace) -> dict[str, str]:
    if args.timeout_seconds < 1: raise AssetError("timeout-seconds must be positive", path="--timeout-seconds", code="cli_error", exit_code=2)
    document = load_request(args.request.resolve())
    work, output, asset_root = _validate_roots(args.work_dir, args.output_dir, args.asset_root)
    work.mkdir(parents=True); log = work / "run.log"
    request_copy = work / "deck-build-request.json"; _write_json(request_copy, document)
    runtime_manifest = work / "runtime-manifest.json"
    # The environment checker is also the manifest producer.  It must run before
    # an asset is staged or a Node builder is started, so a failed host never
    # leaves a partly built deck in the delivery location.
    preflight = [sys.executable, str(SCRIPT_DIR / "verify_install.py"), "--python", sys.executable, "--manifest", str(runtime_manifest)]
    if args.node is not None: preflight += ["--node", str(args.node.resolve())]
    _subprocess(preflight, timeout=args.timeout_seconds, component="environment_preflight", exit_code=5, log=log)
    staged = stage_assets(document, asset_root, work / "assets")
    staged_path = work / "staged-assets.json"; _write_json(staged_path, staged)
    node = str(args.node.resolve()) if args.node is not None else os.environ.get("IVT_NODE", "node")
    pptx = work / "editable-deck.pptx"; build_report = work / "build-report.json"
    _subprocess([node, str(SCRIPT_DIR / "build_deck.mjs"), "--request", str(request_copy), "--staged-assets", str(staged_path), "--output", str(pptx), "--report", str(build_report)], timeout=args.timeout_seconds, component="build", exit_code=6, log=log)
    dimensions = DIMENSIONS[document["output_ratio"]]
    rendered = work / "rendered"; render_report = work / "render-report.json"
    _subprocess([sys.executable, str(SCRIPT_DIR / "render_reconstruction_deck.py"), "--input", str(pptx), "--output-dir", str(rendered), "--report", str(render_report), "--width-px", str(dimensions["width_px"]), "--height-px", str(dimensions["height_px"]), "--timeout-seconds", str(args.timeout_seconds)], timeout=args.timeout_seconds + 10, component="render", exit_code=7, log=log)
    roundtrip_path = work / "roundtrip-report.json"
    bindings = [{"slide_id": slide["slide_id"], "order": slide["order"]} for slide in document["slides"]]
    try:
        roundtrip = run_roundtrip(deck_id=document["deck_id"], candidate_pptx=pptx, slide_bindings=bindings, output=roundtrip_path, width_px=dimensions["width_px"], height_px=dimensions["height_px"], timeout_seconds=args.timeout_seconds)
    except ContractError as exc:
        raise AssetError(str(exc), code="roundtrip_failed", exit_code=7) from exc
    _write_json(roundtrip_path, roundtrip)
    quality_path = work / "quality-report.json"
    quality = verify(request_path=request_copy, pptx=pptx, build_report_path=build_report, staged_assets_path=staged_path, render_report_path=render_report, roundtrip_report_path=roundtrip_path)
    _write_json(quality_path, quality)
    if quality["status"] != "pass": raise AssetError(json.dumps(quality["issues"], ensure_ascii=False), code="structural_qa", exit_code=8)
    ordered = sorted(document["slides"], key=lambda item: item["order"])
    preview = work / "preview.png"
    compose_preview_sheet(slides=[(item["slide_id"], rendered / f"slide-{index:03d}.png") for index, item in enumerate(ordered, 1)], output=preview, title=document["topic"])
    final_pptx, final_preview = _publish(output_dir=output, output_name=document["output_name"], pptx=pptx, preview=preview)
    log_event(log, level="info", component=COMPONENT, event="completed", message="Direct editable deck delivered", run_id=document["task_id"], iteration=None, data={"pptx": str(final_pptx), "preview": str(final_preview)})
    return {"pptx": str(final_pptx.resolve()), "preview": str(final_preview.resolve())}


def main() -> int:
    args = parser().parse_args()
    output_preexisted = args.output_dir.exists()
    try:
        outputs = execute(args)
        print(json.dumps({"status": "ok", "component": COMPONENT, "outputs": outputs, "error": None}, ensure_ascii=False))
        return 0
    except Exception as exc:
        # Never delete a caller-owned pre-existing output directory just because
        # the collision was detected by this invocation.
        if not output_preexisted and args.output_dir.exists(): shutil.rmtree(args.output_dir, ignore_errors=True)
        if isinstance(exc, AssetError): exit_code = exc.exit_code; category = exc.detail.get("code", "runtime_error"); path = exc.detail.get("path", "$")
        elif isinstance(exc, ContractError): exit_code = 4; category = "contract_error"; path = exc.errors[0].get("path", "$") if exc.errors else "$"
        else: exit_code = 70; category = "internal_error"; path = "$"
        print(json.dumps({"status": "error", "component": COMPONENT, "outputs": {}, "error": {"exit_code": exit_code, "category": category, "message": str(exc), "path": path}}, ensure_ascii=False))
        return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
