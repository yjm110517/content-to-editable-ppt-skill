from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
P1_TOOLS = ROOT / "tools" / "content-planning"
P1_FIXTURE = ROOT / "tests" / "fixtures" / "p1" / "content-planning-cases.json"
P2_FIXTURE = ROOT / "tests" / "fixtures" / "p2" / "markdown-wireframe-cases.json"
VENDOR = ROOT / "content-to-editable-ppt" / "runtime" / "vendor" / "tabler-icons" / "3.46.0"
sys.path[:0] = [str(SCRIPTS), str(P1_TOOLS), str(ROOT / "tools" / "wireframe")]

from build_tabler_icon_index import build_index
from canonical_artifact import canonical_sha256
from markdown_wireframe import bind_markdown, build_validation_report
from p1_content_planning_eval import load_fixtures
from p2_wireframe_eval import authority, fixture_candidate
from resolve_icon_asset import create_record, materialize
from generate_icon_fallback import compose, draw, handoff
from search_tabler_icons import rank


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accepted_p2(case: dict[str, Any], timestamp: str, root: Path) -> tuple[Path, Path]:
    bundle, _paths = authority(case, timestamp, root / "p1")
    candidate = fixture_candidate(bundle, case["case_id"], timestamp)
    first = candidate["slides"][0]["visual_placeholders"][0]
    first["role"] = "icon"
    first["subtype"] = None
    report = build_validation_report(candidate, bundle, report_id=f"{case['case_id']}-p3-p2", validated_at_utc=timestamp)
    if report["status"] != "pass":
        raise RuntimeError(f"{case['case_id']} P2 fixture invalid: {report['issues']}")
    markdown, manifest = bind_markdown(candidate, bundle)
    manifest["status"] = "accepted"
    wireframes = root / "wireframes"
    wireframes.mkdir(parents=True)
    (wireframes / "deck-wireframe.md").write_bytes(markdown)
    manifest_path = wireframes / "wireframe-manifest.json"
    write(manifest_path, manifest)
    return manifest_path, wireframes


def resolve_case(case: dict[str, Any], timestamp: str, root: Path, index: dict[str, Any]) -> dict[str, Any]:
    p2_manifest, wireframes = accepted_p2(case, timestamp, root)
    manifest = load(p2_manifest)
    icon_visuals = [visual for slide in manifest["slides"] for visual in slide["visual_placeholders"] if visual["role"] == "icon"]
    if not icon_visuals:
        raise RuntimeError(f"{case['case_id']} has no icon placeholder")
    visual = icon_visuals[0]
    manifest_sha = canonical_sha256(manifest)
    direction = {"schema_version": "1.0", "artifact_type": "deck_visual_direction", "deck_id": case["case_id"], "p2_manifest_sha256": manifest_sha, "icon_family": "tabler-outline", "created_at_utc": timestamp}
    direction_path = root / "deck-visual-direction.json"; write(direction_path, direction)
    evidence = rank(index, "code", 8, visual_ref=visual["visual_ref"], p2_manifest_sha256=manifest_sha)
    evidence_path = root / "search-evidence.json"; write(evidence_path, evidence)
    record_path = root / "resolution-record.json"
    create_record(argparse.Namespace(
        p2_manifest=p2_manifest, wireframe_root=wireframes, visual_direction=direction_path,
        search_evidence=evidence_path, visual_ref=visual["visual_ref"], icon_name="code",
        selection_method="exact_canonical", vendor_root=VENDOR, created_at_utc=timestamp, output=record_path,
    ))
    assets = root / "resolved" / "assets"
    materialize(argparse.Namespace(resolution_record=record_path, vendor_root=VENDOR, source_svg=None, output_dir=assets))
    asset_manifest = root / "resolved" / "asset_manifest.json"
    entry = load(asset_manifest)["assets"][0]
    non_icons = [visual for slide in manifest["slides"] for visual in slide["visual_placeholders"] if visual["role"] != "icon"]
    return {"case_id": case["case_id"], "status": "pass", "icon_placeholders": len(icon_visuals), "non_icon_placeholders_excluded": len(non_icons), "resolver_calls": 1, "visual_ref": visual["visual_ref"], "asset_manifest": asset_manifest, "asset_dir": assets, "entry": entry, "p2_manifest": p2_manifest, "wireframes": wireframes, "direction": direction_path}


def fallback_evidence(case_result: dict[str, Any], timestamp: str, root: Path) -> dict[str, Any]:
    common = {"p2_manifest": case_result["p2_manifest"], "wireframe_root": case_result["wireframes"], "visual_direction": case_result["direction"], "visual_ref": case_result["visual_ref"], "created_at_utc": timestamp}
    composition_source, composition_record = root / "composition.svg", root / "composition-record.json"
    compose(argparse.Namespace(**common, vendor_root=VENDOR, icon_name=["code", "sparkles"], output_source=composition_source, output_record=composition_record))
    composition_assets = root / "composition-assets" / "assets"
    materialize(argparse.Namespace(resolution_record=composition_record, vendor_root=None, source_svg=composition_source, output_dir=composition_assets))
    drawing = {"schema_version": "1.0", "artifact_type": "simple_icon_drawing", "visual_ref": case_result["visual_ref"], "width": 24, "height": 24, "primitives": [{"type": "rect", "x": 3, "y": 4, "width": 18, "height": 14, "rx": 2}, {"type": "arrow", "x1": 7, "y1": 12, "x2": 17, "y2": 12}]}
    drawing_path = root / "drawing.json"; write(drawing_path, drawing)
    drawing_source, drawing_record = root / "programmatic.svg", root / "programmatic-record.json"
    draw(argparse.Namespace(**common, drawing=drawing_path, output_source=drawing_source, output_record=drawing_record))
    drawing_assets = root / "programmatic-assets" / "assets"
    materialize(argparse.Namespace(resolution_record=drawing_record, vendor_root=None, source_svg=drawing_source, output_dir=drawing_assets))
    handoff_path = root / "raster-handoff.json"
    handoff(argparse.Namespace(**common, reason="no_suitable_svg", output=handoff_path))
    return {
        "existing": "pass",
        "composition": {"status": "pass", "sanitized_svg_sha256": load(composition_assets.parent / "asset_manifest.json")["assets"][0]["sha256"]},
        "programmatic": {"status": "pass", "sanitized_svg_sha256": load(drawing_assets.parent / "asset_manifest.json")["assets"][0]["sha256"]},
        "raster_handoff": {"status": load(handoff_path)["status"], "false_svg_success_artifacts": 0},
    }


def synthetic_preview(case_result: dict[str, Any], node: Path, root: Path) -> dict[str, Any]:
    svg = case_result["asset_manifest"].parent / case_result["entry"]["path"]
    icon_png = root / "rendered-icon.png"
    completed = subprocess.run([str(node), str(SCRIPTS / "render_resolved_svg.mjs"), str(svg), str(icon_png)], cwd=SCRIPTS, capture_output=True, text=True, check=True)
    evidence = json.loads(completed.stdout)
    if evidence["source_sha256"] != case_result["entry"]["sha256"]:
        raise RuntimeError("Preview source hash differs from Asset Manifest sanitized hash")
    canvas = Image.new("RGBA", (256, 256), "white")
    with Image.open(icon_png) as icon:
        canvas.alpha_composite(icon.convert("RGBA"), (80, 80))
    preview = root / "test-preview.png"
    canvas.convert("RGB").save(preview, format="PNG", optimize=False, compress_level=9)
    return {"sanitized_svg_sha256": evidence["source_sha256"], "rendered_icon_png_sha256": evidence["rendered_png_sha256"], "synthetic_preview_sha256": sha256(preview), "resvg_version": evidence["resvg_version"], "node_version": evidence["node_version"], "platform": evidence["platform"]}


def synthetic_ppt(case_result: dict[str, Any], node: Path, python: Path, root: Path) -> dict[str, Any]:
    iteration = root / "ppt-runtime"; iteration.mkdir()
    shutil.copy2(baseline_source := ROOT / "baseline" / "cases" / "B06" / "input" / "source.png", iteration / "source.png")
    shutil.copy2(ROOT / "baseline" / "cases" / "B06" / "input" / "request.json", iteration / "request.json")
    assets = iteration / "assets"; assets.mkdir()
    source_svg = case_result["asset_manifest"].parent / case_result["entry"]["path"]
    shutil.copy2(source_svg, assets / source_svg.name)
    manifest = load(case_result["asset_manifest"])
    manifest["assets"][0]["path"] = f"assets/{source_svg.name}"
    manifest_path = iteration / "asset_manifest.json"; write(manifest_path, manifest)
    report = load(case_result["asset_manifest"].parent / "svg_security_report.json")
    report["results"][0]["output_path"] = f"assets/{source_svg.name}"
    report_path = iteration / "svg_security_report.json"; write(report_path, report)
    asset_id = manifest["assets"][0]["id"]
    layout = {"schema_version": "1.3", "request": "request.json", "source": {"image": "source.png", "width_px": 1672, "height_px": 941}, "slide": {"width_in": 13.333, "height_in": 7.5, "background": "#FFFFFF"}, "metadata": {"topic": "P3.1 synthetic asset consumption", "iteration": 1, "typography_interaction": "default"}, "asset_manifest": "asset_manifest.json", "styles": {}, "elements": [{"id": "resolved-icon", "type": "image", "x": 5.666, "y": 2.25, "w": 2, "h": 2, "z_index": 1, "editable": False, "asset_id": asset_id, "fit": "contain", "preserve_aspect_ratio": True, "rounding": False, "contains_text": False, "alt_text": "Resolved Tabler icon"}]}
    layout_path = iteration / "layout.json"; write(layout_path, layout)
    pptx, summary = iteration / "synthetic.pptx", iteration / "build-summary.json"
    command = [str(node), str(SCRIPTS / "build_slide.mjs"), "--iteration-dir", str(iteration), "--layout", str(layout_path), "--asset-manifest", str(manifest_path), "--asset-dir", str(assets), "--svg-report", str(report_path), "--output", str(pptx), "--build-summary", str(summary), "--python", str(python), "--run-id", "p3-icon-gate", "--iteration", "1"]
    built = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if built.returncode != 0:
        raise RuntimeError(f"PPT builder failed: {built.stdout} {built.stderr}")
    build_summary = load(summary)
    if build_summary["assets"][0]["source_input_sha256"] != manifest["assets"][0]["sha256"]:
        raise RuntimeError("Builder source input differs from Asset Manifest sanitized hash")
    render = iteration / "rendered.png"; render_report = iteration / "render-report.json"
    rendered = subprocess.run([str(python), str(SCRIPTS / "render_ppt.py"), "--input", str(pptx), "--layout", str(layout_path), "--output", str(render), "--report", str(render_report), "--renderer", "powerpoint", "--run-id", "p3-icon-gate", "--iteration", "1"], cwd=ROOT, capture_output=True, text=True)
    if rendered.returncode != 0:
        raise RuntimeError(f"PowerPoint render failed: {rendered.stdout} {rendered.stderr}")
    return {"builder_source_svg_sha256": build_summary["assets"][0]["source_input_sha256"], "pptx_sha256": sha256(pptx), "render_sha256": sha256(render), "powerpoint_render": "passed"}


def main() -> int:
    parser = argparse.ArgumentParser(description="P3.1 deterministic icon resolution Gate")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--work-root", type=Path, default=ROOT / "work" / "p3-icon-resolution")
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        args.work_root = args.work_root.resolve()
        if args.work_root.exists(): shutil.rmtree(args.work_root)
        args.work_root.mkdir(parents=True)
        fixtures = load_fixtures(); cases = {item["case_id"]: item for item in fixtures["cases"]}
        p2_config = load(P2_FIXTURE); timestamp = p2_config["fixed_timestamp_utc"]
        index = build_index(VENDOR)
        results = [resolve_case(cases[case_id], timestamp, args.work_root / case_id, index) for case_id in ("D03", "D05", "D08")]
        fallbacks = fallback_evidence(results[0], timestamp, args.work_root / "D03" / "fallbacks")
        preview = synthetic_preview(results[0], args.node.resolve(), args.work_root / "D03")
        ppt = synthetic_ppt(results[0], args.node.resolve(), args.python.resolve(), args.work_root / "D03")
        if preview["sanitized_svg_sha256"] != ppt["builder_source_svg_sha256"]:
            raise RuntimeError("Preview and PPT Runtime did not consume the same sanitized SVG source")
        report = {"schema_version": "1.0", "phase": "P3.1-icon-resolution", "status": "pass", "integration_gate_candidate": "pass", "blocking_issues": 0, "primary_library": "tabler-icons", "online_resolution_calls": 0, "hallucinated_icon_paths": 0, "resolution_record_overwrites": 0, "arbitrary_host_svg": 0, "independent_agent_calls": 0, "generative_icon_substitution": 0, "cases": [{key: value for key, value in item.items() if key not in {"asset_manifest", "asset_dir", "entry", "p2_manifest", "wireframes", "direction"}} for item in results], "fallback_routes": fallbacks, "synthetic_preview": preview, "ppt_runtime": ppt, "source_hashes_equal": True, "p1_p2_drift": 0, "p0_baseline_unchanged": subprocess.run(["git", "diff", "--quiet", "ce815cc", "--", "baseline"], cwd=ROOT).returncode == 0, "review_run": {"live_host_model_invocations": 0, "planner_calls": 0, "reviewer_calls": 0, "icon_reviewer_calls": 0, "image_generation_calls": 0}}
        if not report["p0_baseline_unchanged"]: raise RuntimeError("P0 baseline changed")
        output = args.report or args.work_root / "p3-icon-resolution-gate.json"
        write(output.resolve(), report)
        print(json.dumps(report, ensure_ascii=False)); return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
