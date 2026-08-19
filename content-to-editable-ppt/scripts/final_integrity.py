from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decoded_rgb_sha256(path: Path) -> str:
    """Decoded RGB hash: sha256 of the decoded RGB pixel bytes, independent of PNG container bytes."""
    with Image.open(path) as image:
        image.load()
        pixels = image.convert("RGB").tobytes()
    return hashlib.sha256(pixels).hexdigest()


def render_candidate_pptx(
    *,
    pptx_path: Path,
    output_dir: Path,
    report_path: Path,
    width_px: int,
    height_px: int,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    """Re-render the P4 candidate through PowerPoint COM into a NEW output directory (never overwrites P4 artifacts)."""
    if output_dir.exists() or report_path.exists():
        raise ContractError([error("$.output_dir", "P5 render output already exists", "output_conflict")])
    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "render_reconstruction_deck.py"),
        "--input", str(pptx_path.resolve()),
        "--output-dir", str(output_dir.resolve()),
        "--report", str(report_path.resolve()),
        "--width-px", str(width_px),
        "--height-px", str(height_px),
        "--timeout-seconds", str(timeout_seconds),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_seconds + 60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if completed.returncode:
        raise ContractError([error("$.render", completed.stdout.strip() or completed.stderr.strip(), "powerpoint_render_failed")])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return report


def verify_final_integrity(
    *,
    bundle: dict[str, Any],
    candidate_pptx: Path,
    p4_render_root: Path,
    p5_render_dir: Path,
    p5_render_report_path: Path,
    width_px: int,
    height_px: int,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    """Step 1: candidate SHA. Step 2: renderer identity. Step 3: re-render + decoded RGB comparison."""
    p4_render = bundle["p4_render_report"]
    failures: list[dict[str, str]] = []

    candidate_sha = file_sha256(candidate_pptx)
    if candidate_sha != bundle["p4_candidate_pptx_sha256"]:
        raise ContractError([error("$.candidate_pptx", "P5 candidate hash differs from P4 candidate deck", "candidate_hash_mismatch")])

    if p4_render.get("renderer") != "Microsoft PowerPoint":
        failures.append(error("$.p4_render_report.renderer", "P4 renderer evidence is not Microsoft PowerPoint", "render_runtime_mismatch"))
    if p4_render.get("width_px") != width_px or p4_render.get("height_px") != height_px:
        failures.append(error("$.dimensions", "P5 render dimensions differ from P4 renderer evidence", "render_runtime_mismatch"))

    render_report = render_candidate_pptx(
        pptx_path=candidate_pptx,
        output_dir=p5_render_dir,
        report_path=p5_render_report_path,
        width_px=width_px,
        height_px=height_px,
        timeout_seconds=timeout_seconds,
    )
    if render_report.get("renderer_version") != p4_render.get("renderer_version"):
        raise ContractError([error("$.renderer_version", f"PowerPoint renderer version changed: {p4_render.get('renderer_version')} -> {render_report.get('renderer_version')}", "render_runtime_mismatch")])

    p4_by_order = {item["order"]: item for item in p4_render.get("slides", [])}
    p5_slides: list[dict[str, Any]] = []
    for item in sorted(render_report.get("slides", []), key=lambda slide: slide["order"]):
        p4_slide = p4_by_order.get(item["order"])
        if p4_slide is None:
            failures.append(error(f"$.slides[{item['order']}]", "P4 render evidence is missing this slide", "final_render_identity_mismatch"))
            continue
        p4_png = p4_render_root / p4_slide["path"]
        p4_decoded = decoded_rgb_sha256(p4_png) if p4_png.is_file() else None
        if p4_decoded is None:
            failures.append(error(f"$.slides[{item['order']}].p4_png", "P4 post-assembly render PNG is missing", "final_render_identity_mismatch"))
        p5_png = p5_render_dir / item["path"]
        p5_decoded = decoded_rgb_sha256(p5_png)
        if p4_decoded is not None and p4_decoded != p5_decoded:
            failures.append(error(f"$.slides[{item['order']}].decoded_rgb_sha256", "P5 final render decoded RGB differs from P4 post-assembly render", "final_render_identity_mismatch"))
        p5_slides.append({
            "order": item["order"],
            "path": item["path"],
            "png_sha256": item["sha256"],
            "decoded_rgb_sha256": p5_decoded,
            "p4_decoded_rgb_sha256": p4_decoded,
        })

    manifest = {
        "schema_version": "1.0",
        "artifact_type": "p5_final_render_manifest",
        "deck_id": bundle["deck_id"],
        "renderer": render_report.get("renderer"),
        "renderer_version": render_report.get("renderer_version"),
        "width_px": render_report.get("width_px"),
        "height_px": render_report.get("height_px"),
        "ppt_sha256": candidate_sha,
        "slides": p5_slides,
        "p4_inheritance": {
            "p4_candidate_render_report_sha256": canonical_sha256(p4_render),
            "p4_post_assembly_report_sha256": canonical_sha256(bundle["p4_drift_report"]),
            "p4_fidelity_inherited": True,
        },
        "status": "fail" if failures else "pass",
    }
    if failures:
        raise ContractError(failures)
    validate_schema("p5_final_render_manifest", manifest, SCHEMA_DIR)
    return manifest
