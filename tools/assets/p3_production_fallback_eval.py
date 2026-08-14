from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
P1_TOOLS = ROOT / "tools" / "content-planning"
P1_FIXTURE = ROOT / "tests" / "fixtures" / "p1" / "content-planning-cases.json"
P2_FIXTURE = ROOT / "tests" / "fixtures" / "p2" / "markdown-wireframe-cases.json"
VENDOR = ROOT / "content-to-editable-ppt" / "runtime" / "vendor" / "tabler-icons" / "3.46.0"
HISTORICAL_REPORT = ROOT / "reports" / "p3" / "p3-icon-resolution-gate.json"
sys.path[:0] = [str(SCRIPTS), str(P1_TOOLS), str(ROOT / "tools" / "wireframe")]

from build_tabler_icon_index import build_index
from canonical_artifact import canonical_sha256
from generate_icon_fallback import create_handoff, record_decision
from markdown_wireframe import bind_markdown, build_validation_report
from p1_content_planning_eval import load_fixtures
from p2_wireframe_eval import authority, fixture_candidate
from resolve_icon_asset import create_record, materialize, verify
from schema_utils import ContractError
from search_tabler_icons import rank


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accepted_p2(case: dict[str, Any], timestamp: str, root: Path) -> tuple[Path, Path, dict[str, Any]]:
    bundle, _paths = authority(case, timestamp, root / "p1")
    candidate = fixture_candidate(bundle, case["case_id"], timestamp)
    first = candidate["slides"][0]["visual_placeholders"][0]
    first["role"] = "icon"
    first["subtype"] = None
    report = build_validation_report(candidate, bundle, report_id=f"{case['case_id']}-p3-production", validated_at_utc=timestamp)
    if report["status"] != "pass":
        raise RuntimeError(f"{case['case_id']} P2 fixture invalid: {report['issues']}")
    markdown, manifest = bind_markdown(candidate, bundle)
    manifest["status"] = "accepted"
    wireframes = root / "wireframes"
    wireframes.mkdir(parents=True)
    (wireframes / "deck-wireframe.md").write_bytes(markdown)
    manifest_path = wireframes / "wireframe-manifest.json"
    write(manifest_path, manifest)
    return manifest_path, wireframes, first


def direction(manifest: dict[str, Any], manifest_sha: str, timestamp: str, path: Path) -> Path:
    result = {
        "schema_version": "1.0", "artifact_type": "deck_visual_direction",
        "deck_id": manifest["deck_id"], "p2_manifest_sha256": manifest_sha,
        "icon_family": "tabler-outline", "created_at_utc": timestamp,
    }
    write(path, result)
    return path


def resolve_case(
    case: dict[str, Any], timestamp: str, root: Path, index: dict[str, Any],
    *, query: str, selection_method: str,
) -> dict[str, Any]:
    manifest_path, wireframes, visual = accepted_p2(case, timestamp, root)
    manifest = load(manifest_path)
    manifest_sha = canonical_sha256(manifest)
    direction_path = direction(manifest, manifest_sha, timestamp, root / "deck-visual-direction.json")
    evidence = rank(index, query, 8, visual_ref=visual["visual_ref"], p2_manifest_sha256=manifest_sha)
    evidence_path = root / "search-evidence.json"
    write(evidence_path, evidence)
    icon_name = evidence["automatic_icon_name"] if selection_method != "host_from_top_k" else evidence["top_k"][0]["name"]
    selection_path = None
    if selection_method == "host_from_top_k":
        selection_path = root / "selection-decision.json"
        record_decision(argparse.Namespace(
            p2_manifest=manifest_path, wireframe_root=wireframes, visual_direction=direction_path,
            search_evidence=evidence_path, visual_ref=visual["visual_ref"], created_at_utc=timestamp,
            decision="select_tabler", selected_icon=icon_name, output=selection_path,
        ))
    record_path = root / "resolution-record.json"
    create_record(argparse.Namespace(
        p2_manifest=manifest_path, wireframe_root=wireframes, visual_direction=direction_path,
        search_evidence=evidence_path, visual_ref=visual["visual_ref"], icon_name=icon_name,
        selection_method=selection_method, selection_decision=selection_path,
        vendor_root=VENDOR, created_at_utc=timestamp, output=record_path,
    ))
    assets = root / "resolved" / "assets"
    materialize(argparse.Namespace(resolution_record=record_path, vendor_root=VENDOR, output_dir=assets))
    verify(argparse.Namespace(
        p2_manifest=manifest_path, wireframe_root=wireframes, visual_direction=direction_path,
        search_evidence=evidence_path, selection_decision=selection_path,
        resolution_record=record_path, vendor_root=VENDOR,
        asset_manifest=assets.parent / "asset_manifest.json",
        security_report=assets.parent / "svg_security_report.json",
        consumption_contract=assets.parent / "consumption-contract.json",
    ))
    entry = load(assets.parent / "asset_manifest.json")["assets"][0]
    return {
        "case_id": case["case_id"], "status": "pass", "selection_method": selection_method,
        "icon_name": icon_name, "sanitized_svg_sha256": entry["sha256"],
    }


def handoff_case(case: dict[str, Any], timestamp: str, root: Path, index: dict[str, Any]) -> dict[str, Any]:
    manifest_path, wireframes, visual = accepted_p2(case, timestamp, root)
    manifest = load(manifest_path)
    manifest_sha = canonical_sha256(manifest)
    direction_path = direction(manifest, manifest_sha, timestamp, root / "deck-visual-direction.json")
    evidence = rank(index, "artificial intelligence code", 8, visual_ref=visual["visual_ref"], p2_manifest_sha256=manifest_sha)
    if evidence["status"] != "host_selection_required":
        raise RuntimeError("handoff fixture unexpectedly auto-selected an icon")
    evidence_path = root / "search-evidence.json"
    write(evidence_path, evidence)
    decision_path = root / "selection-decision.json"
    common = {
        "p2_manifest": manifest_path, "wireframe_root": wireframes, "visual_direction": direction_path,
        "search_evidence": evidence_path, "visual_ref": visual["visual_ref"], "created_at_utc": timestamp,
    }
    record_decision(argparse.Namespace(**common, decision="raster_handoff", selected_icon=None, output=decision_path))
    output = root / "raster-handoff-pending.json"
    create_handoff(argparse.Namespace(**common, selection_decision=decision_path, output=output))
    forbidden = [root / name for name in ("asset_manifest.json", "svg_security_report.json", "consumption-contract.json")]
    false_success = sum(path.exists() for path in forbidden) + len(list(root.rglob("*.svg")))
    return {"status": load(output)["status"], "false_svg_success_artifacts": false_success}


def legacy_rejection(root: Path) -> dict[str, Any]:
    methods = ("tabler_composition", "programmatic_svg")
    rejected = []
    for method in methods:
        record = {
            "schema_version": "1.0", "artifact_type": "icon_resolution_record", "visual_ref": "S01-V01",
            "p2_manifest_sha256": "a" * 64, "resolution_method": method, "source_sha256": "b" * 64,
            "selection_method": "bounded_fallback", "created_at_utc": "2026-08-14T00:00:00Z",
        }
        path = root / f"{method}.json"
        write(path, record)
        try:
            materialize(argparse.Namespace(resolution_record=path, vendor_root=VENDOR, output_dir=root / method / "assets"))
        except ContractError as exc:
            codes = {item["code"] for item in exc.errors}
            if "production_resolution_method_forbidden" not in codes:
                raise RuntimeError(f"unexpected rejection for {method}: {codes}") from exc
            rejected.append(method)
        else:
            raise RuntimeError(f"legacy method entered production: {method}")
    return {"rejected_methods": rejected, "production_calls": 0}


def static_route_check() -> dict[str, Any]:
    production = [
        SCRIPTS / "generate_icon_fallback.py", SCRIPTS / "resolve_icon_asset.py",
        ROOT / "content-to-editable-ppt" / "SKILL.md",
        ROOT / "content-to-editable-ppt" / "references" / "icon-asset-resolution.md",
    ]
    forbidden_patterns = ("from tools.legacy", "import icon_fallback_experiments", "compose(", "draw(")
    hits = []
    for path in production:
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            if pattern in text:
                hits.append(f"{path.relative_to(ROOT)}:{pattern}")
    if hits:
        raise RuntimeError(f"formal route still references legacy fallback: {hits}")
    gate_tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(gate_tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("tools.legacy"):
            hits.append(f"{Path(__file__).relative_to(ROOT)}:legacy import")
        if isinstance(node, ast.Import) and any(alias.name.startswith("tools.legacy") for alias in node.names):
            hits.append(f"{Path(__file__).relative_to(ROOT)}:legacy import")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"compose", "draw"}:
            hits.append(f"{Path(__file__).relative_to(ROOT)}:{node.func.id} call")
    if hits:
        raise RuntimeError(f"formal Gate still references legacy fallback: {hits}")
    return {"status": "pass", "legacy_imports_or_calls": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description="P3.1 production fallback cutover Gate")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--work-root", type=Path, default=ROOT / "work" / "p3-production-fallback")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        work_root = args.work_root.resolve()
        if work_root.exists():
            shutil.rmtree(work_root)
        work_root.mkdir(parents=True)
        fixtures = load_fixtures()
        cases = {item["case_id"]: item for item in fixtures["cases"]}
        timestamp = load(P2_FIXTURE)["fixed_timestamp_utc"]
        index = build_index(VENDOR)
        results = [
            resolve_case(cases["D03"], timestamp, work_root / "D03", index, query="code", selection_method="exact_canonical_name"),
            resolve_case(cases["D05"], timestamp, work_root / "D05", index, query="2fa", selection_method="exact_official_alias"),
            resolve_case(cases["D08"], timestamp, work_root / "D08", index, query="artificial intelligence code", selection_method="host_from_top_k"),
        ]
        handoff = handoff_case(cases["D03"], timestamp, work_root / "handoff", index)
        if handoff["false_svg_success_artifacts"]:
            raise RuntimeError("Raster Handoff created false SVG success artifacts")
        report = {
            "schema_version": "1.0",
            "phase": "P3.1-production-fallback-cutover",
            "status": "pass",
            "blocking_issues": 0,
            "production_routes": results,
            "raster_handoff": handoff,
            "legacy_isolation": legacy_rejection(work_root / "legacy-rejection"),
            "static_route_check": static_route_check(),
            "historical_gate_report_sha256": sha256(HISTORICAL_REPORT),
            "p0_baseline_unchanged": subprocess.run(["git", "diff", "--quiet", "ce815cc", "--", "baseline"], cwd=ROOT).returncode == 0,
            "review_run": {
                "live_host_model_invocations": 0, "planner_calls": 0, "reviewer_calls": 0,
                "icon_reviewer_calls": 0, "image_generation_calls": 0, "powerpoint_calls": 0,
            },
        }
        if not report["p0_baseline_unchanged"]:
            raise RuntimeError("P0 baseline changed")
        output = (args.report or work_root / "p3-production-fallback-cutover-gate.json").resolve()
        write(output, report)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
