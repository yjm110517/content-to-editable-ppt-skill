from __future__ import annotations

import argparse
import copy
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
D03_CALL = ROOT / "reports" / "p2" / "d03-markdown-host-call"
sys.path[:0] = [str(SCRIPTS), str(P1_TOOLS)]

from canonical_artifact import canonical_sha256
from markdown_wireframe import audit_markdown, bind_markdown, build_validation_report, load_markdown_authority
from p1_content_planning_eval import evaluate_case as evaluate_p1_case
from schema_utils import validate_schema


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def authority(case: dict[str, Any], timestamp: str, root: Path) -> tuple[dict[str, Any], dict[str, Path]]:
    evaluate_p1_case(case, timestamp, root)
    source = root / case["case_id"]
    content = source / "slide-content"
    content.mkdir()
    projection = load(source / "projection_manifest.json")
    for item in projection["slides"]:
        source_slide = source / f"approved_slide_content_{item['slide_id']}.json"
        shutil.copyfile(source_slide, content / item["path"])
    write(content / "projection-manifest.json", projection)
    paths = {"p1": source / "content_plan_state.json", "outline": source / "approved_outline.json", "content": content}
    return load_markdown_authority(p1_state_path=paths["p1"], approved_outline_path=paths["outline"], slide_content_dir=content), paths


def fixture_candidate(bundle: dict[str, Any], case_id: str, timestamp: str) -> dict[str, Any]:
    slides = []
    for content in sorted(bundle["slide_contents"].values(), key=lambda value: value["order"]):
        items = [content["title"], *sorted(content["content_blocks"], key=lambda value: value["order"])]
        tokens = [f"{{{{p2:content-ref={item['content_ref']}}}}}" for item in items]
        draft = "┌─" + tokens[0] + "─┐\n│" + " → ".join(tokens[1:] + ["{{p2:zone=diagram}}"] if len(tokens) > 1 else ["{{p2:zone=diagram}}"] ) + "│\n└────────┘"
        slides.append({"slide_id": content["slide_id"], "order": content["order"], "layout_draft": draft,
                       "content_labels": [{"content_ref": item["content_ref"], "label": item["text"] if len(item["text"]) <= 24 else item["text"][:12]} for item in items],
                       "layout_notes": "标题置顶，内容按编号顺序阅读，右侧或下方预留结构示意区。"})
    return {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_type": "markdown_wireframe_candidate",
            "artifact_id": f"{case_id}-markdown-wireframe-r1", "deck_id": case_id, "revision": 1, "parent_sha256": None,
            "pass_id": "initial-fixture", "host_model_invocation_id": f"{case_id}-fixture-not-live", "slides": slides, "created_at_utc": timestamp}


def evaluate(case: dict[str, Any], config: dict[str, Any], timestamp: str, root: Path) -> dict[str, Any]:
    bundle, paths = authority(case, timestamp, root / "p1")
    candidate = copy.deepcopy(config["candidate"]) if "candidate" in config else fixture_candidate(bundle, case["case_id"], timestamp)
    report = build_validation_report(candidate, bundle, report_id=f"{case['case_id']}-markdown-validation", validated_at_utc=timestamp)
    if report["status"] != "pass":
        raise RuntimeError(f"{case['case_id']} Candidate failed: {report['issues']}")
    first, manifest = bind_markdown(candidate, bundle)
    second, second_manifest = bind_markdown(candidate, bundle)
    if first != second or manifest != second_manifest:
        raise RuntimeError(f"{case['case_id']} Markdown is non-deterministic")
    audit_markdown(first, manifest, bundle)
    target = root / case["case_id"]
    target.mkdir(parents=True, exist_ok=True)
    (target / "deck-wireframe.md").write_bytes(first)
    write(target / "wireframe-manifest.json", {**manifest, "status": "accepted"})
    write(target / "candidate.json", candidate); write(target / "validation-report.json", report)
    if list(target.rglob("*.svg")):
        raise RuntimeError("Formal P2 generated SVG")
    return {"case_id": case["case_id"], "status": "pass", "pages": len(manifest["slides"]),
            "authority_drift": 0, "missing_or_unknown_content_refs": 0,
            "host_model_invocations": config["host_model_invocations"], "contract_corrections": 0,
            "wireframe_sha256": manifest["wireframe_sha256"]}


def verify_d03_call_evidence(bundle: dict[str, Any], fixture_candidate_value: dict[str, Any]) -> dict[str, Any]:
    raw = load(D03_CALL / "raw_response.json")
    record = load(D03_CALL / "call_record.json")
    validate_schema("markdown_wireframe_host_call_record", record, ROOT / "content-to-editable-ppt" / "schemas")
    expected_files = {
        "config_sha256": D03_CALL / "config.json",
        "prompt_sha256": D03_CALL / "prompt.md",
        "output_schema_sha256": ROOT / "content-to-editable-ppt" / "schemas" / "markdown-wireframe-candidate.schema.json",
    }
    for field, path in expected_files.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != record[field]:
            raise RuntimeError(f"D03 Host Call {field} mismatch")
    expected_inputs = {
        "p1_state": canonical_sha256(bundle["p1_state"]),
        "approved_outline": canonical_sha256(bundle["approved_outline"]),
        "projection_manifest": canonical_sha256(bundle["projection_manifest"]),
    }
    if record["input_sha256"] != expected_inputs:
        raise RuntimeError("D03 Host Call input hash mismatch")
    if raw != fixture_candidate_value or canonical_sha256(raw) != canonical_sha256(fixture_candidate_value):
        raise RuntimeError("D03 raw Host response differs from frozen Candidate")
    return {"status": "pass", "host_model_invocations": 1, "candidate_sha256": canonical_sha256(raw)}


def main() -> int:
    parser = argparse.ArgumentParser(description="P2 deterministic Markdown Wireframe evaluation")
    parser.add_argument("--all", action="store_true"); parser.add_argument("--case", choices=["D03", "D05", "D08"])
    parser.add_argument("--work-root", type=Path, default=ROOT / "work" / "p2-markdown-wireframe")
    args = parser.parse_args()
    p1 = load(P1_FIXTURE); p2 = load(P2_FIXTURE); cases = {item["case_id"]: item for item in p1["cases"]}
    selected = [args.case] if args.case else (["D03", "D05", "D08"] if args.all else ["D03"])
    try:
        if args.work_root.exists(): shutil.rmtree(args.work_root)
        results = [evaluate(cases[item], p2["cases"][item], p2["fixed_timestamp_utc"], args.work_root.resolve()) for item in selected]
        d03_bundle, _ = authority(cases["D03"], p2["fixed_timestamp_utc"], args.work_root.resolve() / "d03-call-authority")
        d03_evidence = verify_d03_call_evidence(d03_bundle, p2["cases"]["D03"]["candidate"])
        baseline = subprocess.run(["git", "diff", "--quiet", "ce815cc", "--", "baseline"], cwd=ROOT).returncode == 0
        if not baseline: raise RuntimeError("P0 Baseline differs from ce815cc")
        report = {"schema_version": "1.0", "phase": "P2-markdown", "status": "pass", "integration_gate_candidate": "pass",
                  "cases": results, "blocking_issues": 0, "authority_drift": 0, "missing_or_unknown_content_refs": 0,
                  "formal_p2_svg_generation": 0, "automatic_redesign": 0, "specialist_agent_calls": 0,
                  "review_run": {"live_host_model_invocations": 0, "planner_calls": 0, "reviewer_calls": 0, "image_generation_calls": 0},
                  "recorded_d03_host_model_invocations": p2["cases"]["D03"]["host_model_invocations"], "p0_baseline_unchanged": True}
        report["d03_host_call_evidence"] = d03_evidence
        write(args.work_root.resolve() / "p2-markdown-wireframe-gate.json", report)
        print(json.dumps(report, ensure_ascii=False)); return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)); return 1


if __name__ == "__main__":
    raise SystemExit(main())
