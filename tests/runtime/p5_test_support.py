"""Deterministic test fixtures. Fake QA is NEVER used for Live validation."""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
SCHEMAS = ROOT / "content-to-editable-ppt" / "schemas"
sys.path.insert(0, str(SCRIPTS))

from agent_common import REFERENCE_DIR, canonical_yaml_hash, load_role, normalized_text_bytes, sha256_bytes
from asset_common import atomic_write_json, sha256_file
from compile_reconstruction_plan import read_source_metadata
from evaluate_review import evaluate
from materialize_reconstruction_handoff import materialize_handoff
from reconstruction_plan import compile_reconstruction_plan
from schema_utils import load_json
from visual_first_planner import content_authority_from_handoff
from tests.runtime.handoff_test_support import materializer_args
from tests.runtime.test_visual_first_planner import geometry, shape, text


def create_work(root: Path, *, version: str = "1.2", native: bool = False) -> Path:
    args = materializer_args(root, SCHEMAS, sha256_file)
    request = load_json(args.work_root / "request.json")
    request["task_id"] = "p5-live-01"
    request["review_policy"]["max_iterations"] = 4
    atomic_write_json(args.work_root / "request.json", request)
    stage1 = load_json(args.stage1_authority)
    slide = stage1["slides"][0]
    slide["objects"] = slide["objects"][:4]
    slide["text_items"][0]["text"] = "Scoped revision"
    slide["structured_data"] = []
    slide["semantic_structure"]["regions"][0]["members"] = ["card-01", "card-02"]
    slide["semantic_structure"]["reading_order"] = ["title-object", "card-01", "card-02"]
    if native:
        from tests.runtime.test_p4_native_data_objects import structured_data
        stage1["schema_version"] = "1.1"
        slide["structured_data"] = structured_data()
        for kind in ("chart", "table"):
            slide["objects"].append({"id": f"{kind}-01", "kind": kind, "role": "data", "data_ref": f"data-{kind}-01"})
            slide["semantic_structure"]["reading_order"].append(f"{kind}-01")
    atomic_write_json(args.stage1_authority, stage1)
    image_path = root / "stage2/designs/S01.png"
    image = Image.new("RGB", (1600, 900), "#FFFFFF")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((144, 315, 544, 540), radius=22, fill="#DDEEFF")
    draw.rounded_rectangle((768, 315, 1168, 540), radius=22, fill="#DDEEFF")
    draw.line((544, 430, 768, 430), fill="#53647A", width=4)
    for offset, color in ((0, "#78AACC"), (35, "#D4E8F0"), (70, "#416885")):
        draw.ellipse((1220 + offset, 230 + offset, 1400 + offset, 400 + offset), fill=color)
    # Test artwork is generated programmatically; it is not a Reviewer result.
    from PIL import ImageFont
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    font = ImageFont.truetype(str(font_path), 48) if font_path.is_file() else ImageFont.load_default()
    draw.text((80, 50), "Scoped revision", fill="#111111", font=font)
    image.save(image_path)
    stage2 = load_json(args.stage2_handoff)
    stage2["stage1_authority_sha256"] = sha256_file(args.stage1_authority)
    stage2["slides"][0]["approved_design"]["sha256"] = sha256_file(image_path)
    stage2["slides"][0]["visual_objects"][0]["id"] = "hero"
    stage2["slides"][0]["visual_objects"][0]["overlaps_with"] = []
    atomic_write_json(args.stage2_handoff, stage2)
    materialize_handoff(args)
    work = args.work_root
    current = work / "iterations/01"
    current.mkdir(parents=True)
    elements = [text("title-object", "S01-title", 0.05, 0.04, 0.9, 0.1, 28),
                shape("card-01", 0.09, 0.35), shape("card-02", 0.48, 0.50),
                {"id": "connector-01", "role": "flow", "representation": "native_connector",
                 "geometry": geometry(0.34, 0.48, 0.14, 0.01), "z_index": 0,
                 "from_id": "card-01", "to_id": "card-02", "style": {"line": {"color": "#53647A", "width_pt": 1.5}}},
                {"id": "hero", "role": "hero", "representation": "raster_asset", "z_index": 1,
                 "geometry": geometry(0.76, 0.25, 0.18, 0.30),
                 "asset_request": {"source": "approved_design", "source_region": geometry(0.76, 0.25, 0.18, 0.30), "contains_text": False}}]
    for element in elements[1:3]:
        element["geometry"].update(width=0.25, height=0.25)
    if native:
        from tests.runtime.test_p4_native_data_objects import plan as native_plan
        elements.extend(copy.deepcopy(native_plan()["elements"][1:]))
    plan = {"schema_version": version, "page": {"id": "S01", "iteration": 1},
            "source": {"approved_design": "source.png"}, "slide": {"width_in": 13.333, "height_in": 7.5, "background": "#FFFFFF"},
            "elements": elements}
    if version == "1.2":
        plan["provenance"] = {"reconstruction_handoff_sha256": sha256_file(work / "reconstruction-handoff.json"),
                              "approved_design_sha256": sha256_file(work / "source.png"), "previous_plan_sha256": None, "revision_patch_sha256": None}
    atomic_write_json(current / "reconstruction-plan.json", plan)
    handoff = load_json(work / "reconstruction-handoff.json")
    artifacts = compile_reconstruction_plan(plan, content_authority_from_handoff(handoff), request,
                                            read_source_metadata(work / "source.png"), handoff["structured_data"])
    for key, filename in (("layout", "layout.json"), ("crops", "crops.json"), ("asset_manifest", "asset_manifest.json")):
        atomic_write_json(current / filename, artifacts[key])
    return work


def fake_qa(work: Path, iteration: int = 1) -> None:
    """Synthetic unit-test QA, deliberately marked fixture in provenance and warnings."""
    current = work / f"iterations/{iteration:02d}"
    (current / "fixture.pptx").write_bytes(b"NOT A POWERPOINT FILE: unit test fixture")
    (current / "rendered_slide.png").write_bytes((work / "source.png").read_bytes())
    summary = {"schema_version": "1.3", "run_id": "fixture", "iteration": iteration,
               "hashes": {"layout_sha256": sha256_file(current / "layout.json"), "asset_manifest_sha256": sha256_file(current / "asset_manifest.json"), "output_pptx_sha256": sha256_file(current / "fixture.pptx")},
               "output_pptx": "fixture.pptx", "expected_element_count": 5, "built_element_count": 5,
               "missing_element_ids": [], "unexpected_element_ids": [], "build_order": [], "element_map": [], "assets": [], "connections": [], "warnings": ["unit-test fixture"],
               "typography": {"text_element_count": 1, "run_count": 1, "explicit_run_font_count": 1, "inherited_run_font_count": 0, "unresolved_font_count": 0, "non_default_fit_elements": [], "font_resolutions": []}}
    layout_elements = load_json(current / "layout.json")["elements"]
    summary["build_order"] = [e["id"] for e in layout_elements]
    summary["element_map"] = [{"element_id": e["id"], "type": e["type"], "object_names": [f"ivt:{e['id']}"], "object_count": 1} for e in layout_elements]
    summary["expected_element_count"] = summary["built_element_count"] = len(layout_elements)
    atomic_write_json(current / "build_summary.json", summary)
    metrics = {"slide_count": 1, "required_text_count": 1, "editable_required_text_count": 1, "editable_text_ratio": 1.0,
               "editable_text_status": "applicable", "missing_required_native_objects": 0, "invalid_text_exemptions": 0,
               "expected_element_count": 5, "built_element_count": 5, "missing_element_ids": [], "unexpected_element_ids": [],
               "out_of_bounds_shapes": 0, "missing_media": 0, "font_violations": 0, "rendered_page_count": 1}
    hashes = {f"{key}_sha256": sha256_file(path) for key, path in {
        "source": work / "source.png", "request": work / "request.json", "layout": current / "layout.json",
        "crops": current / "crops.json", "asset_manifest": current / "asset_manifest.json", "build_summary": current / "build_summary.json",
        "ppt": current / "fixture.pptx", "render": current / "rendered_slide.png"}.items()}
    hashes.update(skill_version="1.3", skill_revision="fixture", builder="PptxGenJS", builder_version="fixture",
                  python_version="fixture", pillow_version="fixture", python_pptx_version="fixture", platform="fixture", build_time_utc="2026-01-01T00:00:00Z")
    atomic_write_json(current / "qa_report.json", {"schema_version": "1.3", "status": "pass", "iteration": iteration,
                      "hard_failures": [], "warnings": ["unit-test fixture, not actual QA"], "metrics": metrics,
                      "rendering": {"renderer": "Microsoft PowerPoint", "renderer_version": "fixture-not-executed", "fallback_used": False}, "provenance": hashes})


def write_review(work: Path, iteration: int = 1, target: str = "card-02") -> None:
    current = work / f"iterations/{iteration:02d}"
    request = load_json(work / "request.json")
    cfg, cfg_path, prompt_path, _ = load_role("reviewer", SCHEMAS, mode="review")
    rubric_hash = sha256_file(REFERENCE_DIR / "visual-review-rubric.md")
    agent = {"model_selection_mode": "runtime-default", "requested_model": None, "config_sha256": canonical_yaml_hash(cfg_path),
             "prompt_sha256": sha256_bytes(normalized_text_bytes(prompt_path)), "temperature": 0, "top_p": 1, "seed": None,
             "call_id": "fixture-not-a-model-call", "context_id": "fixture-not-a-model-context", "parent_context_id": None}
    review = {"schema_version": "1.3", "task_id": request["task_id"], "iteration": iteration, "reviewer_recommendation": "revise",
              "scores": {"content_accuracy": 100, "layout_similarity": 80, "typography_similarity": 90, "visual_style_similarity": 85, "asset_quality": 90},
              "issues": [{"id": "issue-01", "severity": "major", "recoverability": "recoverable", "category": "layout", "element_ids": [target], "asset_ids": [],
                          "description": f"TEST ISSUE FIXTURE: {target} is too low", "recommended_action": {"type": "update_element", "element_id": target, "changes": {"geometry.y": "move upward toward card-01 alignment"}}}],
              "mandatory_visual_checks": {name: {"status": "pass", "rationale": "fixture; no Reviewer was run", "issue_ids": []} for name in ("connector_topology", "connector_endpoints", "key_proportions", "crop_boundaries", "background_seams", "visual_depth", "typography_hierarchy")},
              "approved_elements": [item["id"] for item in load_json(current / "reconstruction-plan.json")["elements"] if item["id"] not in {target, "connector-01"}],
              "warnings": ["Test issue fixture, not an actual visual review"],
              "review_context": {"source_sha256": sha256_file(work / "source.png"), "render_sha256": sha256_file(current / "rendered_slide.png"),
                                 "layout_sha256": sha256_file(current / "layout.json"), "qa_report_sha256": sha256_file(current / "qa_report.json"),
                                 "asset_manifest_sha256": sha256_file(current / "asset_manifest.json"), "request_sha256": sha256_file(work / "request.json"),
                                 "review_rubric_sha256": rubric_hash, "reviewer_response_schema_sha256": sha256_file(SCHEMAS / "reviewer-response.schema.json"), "reviewer_role_version": "1.3.0"},
              "agent_provenance": {"planner": agent, "reviewer": agent, "review_rubric_sha256": rubric_hash}}
    atomic_write_json(current / "review_report.json", review)
    result = evaluate(request, load_json(current / "qa_report.json"), review, request_path=work / "request.json", qa_path=current / "qa_report.json", review_path=current / "review_report.json")
    atomic_write_json(current / "review_evaluation.json", result)


def make_patch(work: Path, iteration: int = 1, target: str = "card-02", path: str = "/geometry/y", value: object = 0.40) -> dict:
    current = work / f"iterations/{iteration:02d}"
    return {"schema_version": "1.0", "task_id": load_json(work / "request.json")["task_id"], "page_id": "S01",
            "from_iteration": iteration, "to_iteration": iteration + 1, "base_plan_sha256": sha256_file(current / "reconstruction-plan.json"),
            "based_on_review_sha256": sha256_file(current / "review_report.json"), "based_on_review_evaluation_sha256": sha256_file(current / "review_evaluation.json"),
            "targets": [target], "linked_elements": [], "operations": [{"issue_id": "issue-01", "element_id": target, "path": path, "value": value}], "revision_reason": "unit test scoped setting"}


def apply_args(work: Path, iteration: int = 1) -> argparse.Namespace:
    current = work / f"iterations/{iteration:02d}"
    return argparse.Namespace(work_root=work, current_dir=current, patch=current / "revision_patch.json",
                              next_dir=work / f"iterations/{iteration + 1:02d}", schema_dir=SCHEMAS)


def pipeline(work: Path, iteration: int = 1) -> subprocess.CompletedProcess:
    current = work / f"iterations/{iteration:02d}"
    return subprocess.run([sys.executable, str(SCRIPTS / "run_pipeline.py"), "--request", str(work / "request.json"),
                           "--iteration-dir", str(current), "--output-ppt", str(current / "output.pptx"), "--execution-mode", "diagnostic",
                           "--renderer", "powerpoint", "--schema-dir", str(SCHEMAS), "--run-id", "p5-live-01", "--iteration", str(iteration)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
