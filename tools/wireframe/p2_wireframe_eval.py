from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
P1_TOOLS = ROOT / "tools" / "content-planning"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "p2" / "wireframe-cases.json"
P1_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "p1" / "content-planning-cases.json"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(P1_TOOLS))

from canonical_artifact import canonical_sha256
from p1_content_planning_eval import evaluate_case as evaluate_p1_case
from render_wireframe import audit_svg, render_document
from schema_utils import validate_schema
from wireframe_rules import SCHEMA_DIR, build_manifest, expected_authority, layout_constraints_payload, validate_spec
from wireframe_state import advance, initial_state


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_authority(case: dict[str, Any], *, timestamp: str, root: Path) -> dict[str, Any]:
    evaluate_p1_case(case, timestamp, root)
    target = root / case["case_id"]
    approved = load_json(target / "approved_outline.json")
    request = load_json(target / "deck_request.json")
    p1_state = load_json(target / "content_plan_state.json")
    projection = load_json(target / "projection_manifest.json")
    content_dir = target / "slide-content"
    content_dir.mkdir(exist_ok=True)
    contents: dict[str, dict[str, Any]] = {}
    for item in projection["slides"]:
        content = load_json(target / f"approved_slide_content_{item['slide_id']}.json")
        contents[item["slide_id"]] = content
        write_json(content_dir / item["path"], content)
    write_json(content_dir / "projection-manifest.json", projection)
    return {"root": target, "approved": approved, "request": request, "p1_state": p1_state, "projection": projection, "content_dir": content_dir, "contents": contents}


def layout_requirements(case_id: str, request: dict[str, Any], timestamp: str) -> dict[str, Any]:
    visual_zones = [{"scope": "S01" if case_id != "D05" else "S03", "role": "chart", "minimum_count": 1}]
    result = {
        "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1",
        "artifact_id": f"{case_id}-wireframe-layout-r1", "deck_id": case_id,
        "deck_request_sha256": canonical_sha256(request), "revision": 1, "parent_sha256": None,
        "density": "balanced", "preferred_region_structure": ["modular"],
        "required_visual_zones": visual_zones, "layout_direction": "left_to_right",
        "reserved_areas": {"header_height": 0, "footer_height": 0},
        "cross_slide_structural_consistency": "moderate", "layout_constraints_sha256": "0" * 64,
        "source_classifications": [], "created_at_utc": timestamp,
    }
    result["layout_constraints_sha256"] = canonical_sha256(layout_constraints_payload(result))
    validate_schema("wireframe_layout_requirements", result, SCHEMA_DIR)
    return result


def region(identifier: str, role: str, bbox: tuple[int, int, int, int], *, refs: list[str] | None = None, semantic: list[str] | None = None, parent: str | None = None, level: int = 1, z: int = 10, overlap: str | None = None, emphasis: str = "primary") -> dict[str, Any]:
    x, y, w, h = bbox
    return {"region_id": identifier, "role": role, "parent_region_id": parent, "bbox": {"x": x, "y": y, "w": w, "h": h}, "content_refs": refs or [], "semantic_source_refs": semantic or [], "hierarchy_level": level, "emphasis": emphasis, "z_index": z, "overlap_group": overlap}


def build_specs(authority: dict[str, Any], layout: dict[str, Any], timestamp: str) -> list[dict[str, Any]]:
    approved, request, contents = authority["approved"], authority["request"], authority["contents"]
    specs = []
    for page in approved["pages"]:
        slide_id = page["slide_id"]
        content = contents[slide_id]
        content_refs = [item["content_ref"] for item in content["content_blocks"]]
        complex_page = slide_id == ("S03" if approved["deck_id"] == "D05" else "S01")
        regions = [
            region(f"{slide_id}-ROOT", "container", (500, 500, 9000, 8500), z=0),
            region(f"{slide_id}-TITLE", "title", (800, 800, 8400, 1000), refs=[content["title"]["content_ref"]], parent=f"{slide_id}-ROOT", level=2, z=10),
        ]
        relationships = []
        if complex_page:
            regions.extend([
                region(f"{slide_id}-CONTENT", "content", (800, 2300, 3400, 5200), refs=content_refs, parent=f"{slide_id}-ROOT", level=2, z=10),
                region(f"{slide_id}-CHART", "chart", (4800, 2300, 3800, 5200), semantic=content_refs[:1], parent=f"{slide_id}-ROOT", level=2, z=10),
                region(f"{slide_id}-BADGE", "decoration", (700, 700, 1000, 500), parent=f"{slide_id}-ROOT", level=2, z=20),
            ])
            relationships.extend([
                {"relationship_id": f"{slide_id}-REL", "kind": "association", "from_region_id": f"{slide_id}-CONTENT", "to_region_id": f"{slide_id}-CHART", "direction": "forward"},
                {"relationship_id": f"{slide_id}-OVERLAY", "kind": "overlay", "from_region_id": f"{slide_id}-BADGE", "to_region_id": f"{slide_id}-TITLE", "direction": "none"},
            ])
            focal, pattern = f"{slide_id}-CHART", "chart_focus"
        else:
            regions.append(region(f"{slide_id}-CONTENT", "content", (800, 2300, 8400, 5200), refs=content_refs, parent=f"{slide_id}-ROOT", level=2, z=10))
            focal, pattern = f"{slide_id}-CONTENT", "single_column"
        spec = {
            "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1",
            "artifact_id": f"{approved['deck_id']}-{slide_id}-wireframe-r1", "deck_id": approved["deck_id"], "slide_id": slide_id,
            "revision": 1, "parent_sha256": None,
            "authority": expected_authority(approved_outline=approved, slide_content=content, page=page, layout_requirements=layout, output_ratio=request["output_ratio"]),
            "coordinate_system": "normalized_10000", "output_ratio": request["output_ratio"], "layout_pattern": pattern,
            "focal_region_id": focal, "regions": regions, "relationships": relationships, "created_at_utc": timestamp,
        }
        issues = validate_spec(spec, approved_outline=approved, slide_content=content, page=page, layout_requirements=layout, output_ratio=request["output_ratio"])
        if issues:
            raise RuntimeError(f"{approved['deck_id']} {slide_id} fixture is invalid: {issues}")
        specs.append(spec)
    return specs


def persist_specs(directory: Path, specs: list[dict[str, Any]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        write_json(directory / f"{spec['slide_id']}-r{spec['revision']:03d}.json", spec)


def render_manifest(manifest: dict[str, Any], specs: list[dict[str, Any]], contents: dict[str, dict[str, Any]], output: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = copy.deepcopy(manifest)
    by_slide = {item["slide_id"]: item for item in specs}
    warnings = []
    output.mkdir(parents=True, exist_ok=True)
    for item in result["slides"]:
        if item["build_status"] == "reused" and item["svg_path"] and item["svg_sha256"]:
            existing = output / Path(item["svg_path"]).name
            if not existing.is_file() or hashlib.sha256(existing.read_bytes()).hexdigest() != item["svg_sha256"]:
                raise RuntimeError(f"missing reused SVG: {existing}")
            continue
        spec = by_slide[item["slide_id"]]
        svg, slide_warnings = render_document(spec, contents[item["slide_id"]])
        target = output / f"{item['slide_id']}-r{spec['revision']:03d}.svg"
        if target.exists():
            raise RuntimeError(f"refusing to overwrite {target}")
        target.write_bytes(svg)
        item["svg_path"] = f"wireframes/{target.name}"
        item["svg_sha256"] = hashlib.sha256(svg).hexdigest()
        warnings.extend({"slide_id": item["slide_id"], **warning} for warning in slide_warnings)
        audit_svg(svg, spec=spec, slide_content=contents[item["slide_id"]])
    validate_schema("wireframe_manifest", result, SCHEMA_DIR)
    return result, warnings


def state_for_case(case_id: str, manifest: dict[str, Any], *, user_revision: bool, timestamp: str) -> dict[str, Any]:
    state = initial_state(task_id=f"p2-{case_id.lower()}", deck_id=case_id, absolute_host_model_invocation_ceiling=6 if user_revision else 3)
    for event in ("start_input_validation", "inputs_accepted"):
        state = advance(state, event=event, timestamp_utc=timestamp)
    state = advance(state, event="start_initial_planning", pass_id="initial", host_model_invocation_id=f"{case_id}-host-initial", timestamp_utc=timestamp)
    for event in ("candidate_specs_ready", "start_spec_validation", "specs_accepted", "start_rendering", "rendering_complete", "preview_recorded"):
        state = advance(state, event=event, timestamp_utc=timestamp)
    state["current_artifacts"]["wireframe_manifest_sha256"] = canonical_sha256(manifest)
    if user_revision:
        state = advance(state, event="wait_for_feedback", timestamp_utc=timestamp)
        evidence = canonical_sha256({"message": "move the second page content region"})
        state = advance(state, event="feedback_changes_requested", user_evidence_sha256=evidence, affected_slide_ids=["S02"], timestamp_utc=timestamp)
        state = advance(state, event="start_revision_planning", pass_id="revision-1", user_evidence_sha256=evidence, host_model_invocation_id=f"{case_id}-host-revision-1", timestamp_utc=timestamp)
    else:
        state = advance(state, event="complete_without_feedback", timestamp_utc=timestamp)
    return state


def complete_revision_state(state: dict[str, Any], manifest: dict[str, Any], timestamp: str) -> dict[str, Any]:
    for event in ("candidate_specs_ready", "start_spec_validation", "specs_accepted", "start_rendering", "rendering_complete", "preview_recorded", "complete_without_feedback"):
        state = advance(state, event=event, timestamp_utc=timestamp)
    state["current_artifacts"]["wireframe_manifest_sha256"] = canonical_sha256(manifest)
    return state


def evaluate_case(case: dict[str, Any], config: dict[str, Any], timestamp: str, work_root: Path) -> dict[str, Any]:
    case_id = case["case_id"]
    authority = prepare_authority(case, timestamp=timestamp, root=work_root / "p1-authority")
    target = work_root / case_id
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    layout = layout_requirements(case_id, authority["request"], timestamp)
    write_json(target / "wireframe-layout-requirements.json", layout)
    specs = build_specs(authority, layout, timestamp)
    spec_dir = target / "specs-r001"
    persist_specs(spec_dir, specs)
    manifest = build_manifest(approved_outline=authority["approved"], slide_content_manifest_sha256=canonical_sha256(authority["projection"]), specs=specs, layout_requirements=layout, output_ratio=authority["request"]["output_ratio"], artifact_id=f"{case_id}-wireframes-r1", revision=1, created_at_utc=timestamp)
    rendered, warnings = render_manifest(manifest, specs, authority["contents"], target / "wireframes")
    state = state_for_case(case_id, rendered, user_revision=case_id == "D03", timestamp=timestamp)
    revision_isolation = None
    if case_id == "D03":
        revision_specs = copy.deepcopy(specs)
        changed_id = config["revision_slide_id"]
        changed = next(item for item in revision_specs if item["slide_id"] == changed_id)
        changed["parent_sha256"] = canonical_sha256(next(item for item in specs if item["slide_id"] == changed_id))
        changed["revision"] = 2
        changed["artifact_id"] = f"{case_id}-{changed_id}-wireframe-r2"
        body = next(item for item in changed["regions"] if item["role"] == "content")
        body["bbox"]["x"], body["bbox"]["w"] = 1000, 8000
        spec_dir = target / "specs-r002"
        persist_specs(spec_dir, revision_specs)
        second = build_manifest(approved_outline=authority["approved"], slide_content_manifest_sha256=canonical_sha256(authority["projection"]), specs=revision_specs, layout_requirements=layout, output_ratio=authority["request"]["output_ratio"], artifact_id=f"{case_id}-wireframes-r2", revision=2, parent_sha256=canonical_sha256(rendered), previous_manifest=rendered, changed_slide_ids={changed_id}, created_at_utc=timestamp)
        rendered_second, revision_warnings = render_manifest(second, revision_specs, authority["contents"], target / "wireframes")
        warnings.extend(revision_warnings)
        unchanged = [slide_id for slide_id in authority["contents"] if slide_id != changed_id]
        before, after = {item["slide_id"]: item for item in rendered["slides"]}, {item["slide_id"]: item for item in rendered_second["slides"]}
        revision_isolation = all(before[item]["spec_sha256"] == after[item]["spec_sha256"] and before[item]["svg_sha256"] == after[item]["svg_sha256"] and after[item]["build_status"] == "reused" for item in unchanged)
        if not revision_isolation:
            raise RuntimeError("D03 user revision invalidated an unrelated page")
        rendered = rendered_second
        state = complete_revision_state(state, rendered, timestamp)
    order_only_reuse = None
    if case_id == "D08":
        reordered = copy.deepcopy(authority["approved"])
        reordered["pages"][1]["order"], reordered["pages"][2]["order"] = reordered["pages"][2]["order"], reordered["pages"][1]["order"]
        reordered_manifest = build_manifest(approved_outline=reordered, slide_content_manifest_sha256=canonical_sha256(authority["projection"]), specs=specs, layout_requirements=layout, output_ratio=authority["request"]["output_ratio"], artifact_id=f"{case_id}-wireframes-order-r2", revision=2, parent_sha256=canonical_sha256(rendered), previous_manifest=rendered, created_at_utc=timestamp)
        order_only_reuse = all(item["build_status"] == "reused" for item in reordered_manifest["slides"])
        if not order_only_reuse:
            raise RuntimeError("D08 order-only change rebuilt a page")
    state["page_results"] = [{"slide_id": item["slide_id"], "wireframe_input_sha256": item["wireframe_input_sha256"], "build_status": item["build_status"], "spec_sha256": item["spec_sha256"], "svg_sha256": item["svg_sha256"]} for item in rendered["slides"]]
    validate_schema("wireframe_state", state, SCHEMA_DIR)
    write_json(target / "wireframe-manifest.json", rendered)
    write_json(target / "wireframe-state.json", state)
    if case_id == "D03":
        roles = {item["role"] for item in specs[0]["regions"]}
        contract = {
            "content": "content" in roles,
            "container_child": any(item["parent_region_id"] for item in specs[0]["regions"]),
            "semantic_source_ref": any(item["semantic_source_refs"] for item in specs[0]["regions"]),
            "relationship": any(item["kind"] != "overlay" for item in specs[0]["relationships"]),
            "overlay": any(item["kind"] == "overlay" for item in specs[0]["relationships"]),
        }
        if not all(contract.values()):
            raise RuntimeError(f"D03 Host Contract coverage failed: {contract}")
    else:
        contract = None
    return {
        "case_id": case_id, "status": "pass", "pages": len(specs), "preview_mode": config["preview_mode"],
        "host_contract": contract, "host_wireframe_initial_pass_count": state["counters"]["host_wireframe_initial_pass_count"],
        "host_wireframe_revision_pass_count": state["counters"]["host_wireframe_revision_pass_count"],
        "host_model_invocation_count": state["counters"]["host_model_invocation_count"],
        "specialist_agent_calls": 0, "svg_warnings": len(warnings), "revision_isolation": revision_isolation,
        "order_only_reuse": order_only_reuse, "manifest_sha256": canonical_sha256(rendered),
    }


def four_by_three_gate(timestamp: str, work_root: Path, authority: dict[str, Any]) -> dict[str, Any]:
    request = copy.deepcopy(authority["request"])
    request["output_ratio"] = "4:3"
    layout = layout_requirements("D03", request, timestamp)
    authority43 = {**authority, "request": request}
    document = build_specs(authority43, layout, timestamp)[0]
    svg, _ = render_document(document, authority["contents"][document["slide_id"]])
    if b'viewBox="0 0 1200 900"' not in svg:
        raise RuntimeError("4:3 viewBox gate failed")
    target = work_root / "W43" / "S01.svg"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(svg)
    return {"status": "pass", "view_box": "0 0 1200 900", "sha256": hashlib.sha256(svg).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description="P2 deterministic Wireframe evaluation")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--case", choices=["D03", "D05", "D08"])
    parser.add_argument("--work-root", type=Path, default=ROOT / "work" / "p2-wireframe")
    args = parser.parse_args()
    fixture = load_json(FIXTURE_PATH)
    p1_fixture = load_json(P1_FIXTURE_PATH)
    cases = {item["case_id"]: item for item in p1_fixture["cases"]}
    selected = [args.case] if args.case else (["D03", "D05", "D08"] if args.all else ["D03"])
    try:
        results = [evaluate_case(cases[case_id], fixture["cases"][case_id], fixture["fixed_timestamp_utc"], args.work_root.resolve()) for case_id in selected]
        authority = prepare_authority(cases["D03"], timestamp=fixture["fixed_timestamp_utc"], root=args.work_root.resolve() / "p1-authority-w43")
        ratio = four_by_three_gate(fixture["fixed_timestamp_utc"], args.work_root.resolve(), authority)
        baseline = __import__("subprocess").run(["git", "diff", "--quiet", "ce815cc", "--", "baseline"], cwd=ROOT).returncode == 0
        if not baseline:
            raise RuntimeError("P0 Baseline differs from ce815cc")
        report = {"schema_version": "1.0", "phase": "P2", "status": "pass", "cases": results, "four_by_three": ratio, "p0_baseline_unchanged": baseline, "automatic_wireframe_redesign_count": 0, "specialist_agent_calls": 0, "blocking_issues": 0}
        write_json(args.work_root.resolve() / "p2-wireframe-gate.json", report)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
