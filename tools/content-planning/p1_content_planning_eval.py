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
SCHEMAS = ROOT / "content-to-editable-ppt" / "schemas"
FIXTURES = ROOT / "tests" / "fixtures" / "p1" / "content-planning-cases.json"
sys.path.insert(0, str(SCRIPTS))

from canonical_artifact import canonical_sha256
from content_plan_rules import approved_outline_from, validate_candidate_outline, validate_material_understanding, validate_outline_confirmation, validate_task_route
from content_plan_state import advance, initial_state
from deterministic_project_slide_content import build_projection, verify_projection
from schema_utils import validate_schema


def load_fixtures() -> dict[str, Any]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def user_message_hash(message: str) -> str:
    return canonical_sha256({"message": message})


def build_documents(case: dict[str, Any], timestamp: str) -> dict[str, Any]:
    case_id = case["case_id"]
    route = {
        "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1",
        "task_id": f"p1-{case_id.lower()}", "route_id": f"route-{case_id.lower()}-r1", "revision": 1,
        "parent_route_sha256": None, "route": "content_to_ppt", "intent_summary": case["objective"],
        "evidence": ["fixture requests a new presentation"], "created_at_utc": timestamp,
    }
    deck_request = {
        "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1",
        "task_id": route["task_id"], "deck_id": case_id, "topic": case["topic"], "objective": case["objective"],
        "audience": case["audience"], "language": "zh-CN", "page_count": len(case["candidates"][-1]["pages"]),
        "output_ratio": "16:9", "source_material_ids": ["M01"], "must_preserve": [], "prohibited_changes": [],
        "visual_requirements": [], "external_research": "not_authorized",
    }
    materials = {
        "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": f"{case_id}-materials-r1",
        "deck_id": case_id, "revision": 1, "parent_sha256": None, "external_research": "not_authorized", "status": "ready",
        "materials": [{"material_id": "M01", "display_name": f"{case_id} public fixture", "media_type": "text/plain", "read_status": "readable", "required_for_task": True, "blocking": False, "content_sha256": hashlib.sha256(case["material_text"].encode("utf-8")).hexdigest(), "reason": None}],
        "facts": [{"fact_id": item["id"], "text": item["text"], "kind": "fact", "source_refs": ["M01"]} for item in case["facts"]],
        "warnings": [], "ignore_authorizations": [], "created_at_utc": timestamp,
    }
    candidates = []
    parent_hash = None
    revision_hash = user_message_hash(case["revision_request"]) if case.get("revision_request") else None
    for raw_candidate in case["candidates"]:
        revision = raw_candidate["revision"]
        pages = []
        for index, raw_page in enumerate(raw_candidate["pages"], start=1):
            slide_id = f"S{index:02d}"
            pages.append({
                "slide_id": slide_id, "order": index, "role": raw_page["role"], "purpose": raw_page["purpose"],
                "key_message": raw_page["key_message"], "title": {"content_ref": f"{slide_id}-TITLE", "text": raw_page["title"]},
                "content_blocks": [{"content_ref": f"{slide_id}-C{block_index:02d}", "order": block_index, "text": text, "source_refs": [raw_page["facts"][block_index - 1]]} for block_index, text in enumerate(raw_page["blocks"], start=1)],
                "visual_intent": raw_page["visual_intent"], "source_refs": list(raw_page["facts"]),
            })
        candidate = {
            "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": f"{case_id}-candidate-r{revision}",
            "deck_id": case_id, "revision": revision, "parent_sha256": parent_hash, "material_understanding_sha256": canonical_sha256(materials),
            "host_pass_counts": {"planning": 1, "revision": revision - 1, "automatic_regeneration": 0},
            "pages": pages, "created_at_utc": timestamp,
        }
        if revision > 1:
            candidate["user_revision_request_sha256"] = revision_hash
        candidates.append(candidate)
        parent_hash = canonical_sha256(candidate)
    return {"route": route, "deck_request": deck_request, "materials": materials, "candidates": candidates}


def text_map(pages: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for page in pages:
        result[page["title"]["content_ref"]] = page["title"]["text"]
        result.update({item["content_ref"]: item["text"] for item in page["content_blocks"]})
    return result


def evaluate_case(case: dict[str, Any], timestamp: str, output_root: Path | None = None) -> dict[str, Any]:
    documents = build_documents(case, timestamp)
    route, request, materials, candidates = documents["route"], documents["deck_request"], documents["materials"], documents["candidates"]
    validate_task_route(route, SCHEMAS)
    validate_schema("deck_request", request, SCHEMAS)
    validate_material_understanding(materials, SCHEMAS)
    state = initial_state(task_id=route["task_id"], deck_id=case["case_id"])
    state = advance(state, event="start_routing", timestamp_utc=timestamp)
    state = advance(state, event="route_content_to_ppt", artifact_kind="task_route", artifact_sha256=canonical_sha256(route), timestamp_utc=timestamp)
    state = advance(state, event="materials_ready", artifact_kind="materials", artifact_sha256=canonical_sha256(materials), timestamp_utc=timestamp)

    for index, candidate in enumerate(candidates):
        validate_candidate_outline(candidate, deck_request=request, materials=materials, schema_dir=SCHEMAS)
        if index == 0:
            state = advance(state, event="initial_candidate_ready", artifact_kind="candidate_outline", artifact_sha256=canonical_sha256(candidate), timestamp_utc=timestamp)
        else:
            state = advance(state, event="candidate_revised", artifact_kind="candidate_outline", artifact_sha256=canonical_sha256(candidate), user_evidence_sha256=candidate["user_revision_request_sha256"], timestamp_utc=timestamp)
        state = advance(state, event="request_outline_confirmation", timestamp_utc=timestamp)
        if index < len(candidates) - 1:
            response = {
                "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "confirmation_id": f"{case['case_id']}-changes-r{candidate['revision']}",
                "deck_id": case["case_id"], "candidate_revision": candidate["revision"], "candidate_sha256": canonical_sha256(candidate),
                "status": "changes_requested", "user_message_sha256": user_message_hash(case["revision_request"]), "created_at_utc": timestamp,
            }
            validate_outline_confirmation(candidate, response, SCHEMAS)
            state = advance(state, event="changes_requested", artifact_kind="confirmation", artifact_sha256=canonical_sha256(response), user_evidence_sha256=response["user_message_sha256"], timestamp_utc=timestamp)

    final_candidate = candidates[-1]
    confirmation = {
        "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "confirmation_id": f"{case['case_id']}-confirmed-r{final_candidate['revision']}",
        "deck_id": case["case_id"], "candidate_revision": final_candidate["revision"], "candidate_sha256": canonical_sha256(final_candidate),
        "status": "confirmed", "user_message_sha256": user_message_hash(case["confirmation_message"]), "created_at_utc": timestamp,
    }
    validate_outline_confirmation(final_candidate, confirmation, SCHEMAS)
    approved = approved_outline_from(final_candidate, confirmation, revision=1, parent_sha256=None, approved_at_utc=timestamp)
    validate_schema("approved_outline", approved, SCHEMAS)
    state = advance(state, event="outline_confirmed", artifact_kind="confirmation", artifact_sha256=canonical_sha256(confirmation), user_evidence_sha256=confirmation["user_message_sha256"], timestamp_utc=timestamp)
    state = advance(state, event="approved_outline_recorded", artifact_kind="approved_outline", artifact_sha256=canonical_sha256(approved), timestamp_utc=timestamp)
    slides, projection_manifest = build_projection(approved, frozen_at_utc=timestamp)
    state = advance(state, event="start_projection", timestamp_utc=timestamp)
    for slide in slides:
        verify_projection(approved, slide)
    state = advance(state, event="projection_complete", artifact_kind="slide_content_manifest", artifact_sha256=canonical_sha256(projection_manifest), timestamp_utc=timestamp)
    state = advance(state, event="complete_p1", timestamp_utc=timestamp)
    validate_schema("content_plan_state", state, SCHEMAS)
    projected_pages = [{"title": slide["title"], "content_blocks": slide["content_blocks"]} for slide in slides]
    approved_pages = [{"title": page["title"], "content_blocks": page["content_blocks"]} for page in approved["pages"]]
    if text_map(projected_pages) != text_map(approved_pages):
        raise RuntimeError(f"{case['case_id']} content projection drift")
    expected_revisions = len(candidates) - 1
    expected_counters = {"host_planning_pass_count": 1, "host_revision_pass_count": expected_revisions, "automatic_regeneration_count": 0, "planner_calls": 0, "reviewer_calls": 0}
    if state["counters"] != expected_counters:
        raise RuntimeError(f"{case['case_id']} Host budget mismatch")

    if output_root:
        target = output_root / case["case_id"]
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        artifacts = {**documents, "confirmation": confirmation, "approved_outline": approved, "projection_manifest": projection_manifest, "content_plan_state": state}
        artifacts.pop("candidates")
        artifacts.update({f"candidate_outline_r{item['revision']}": item for item in candidates})
        artifacts.update({f"approved_slide_content_{item['slide_id']}": item for item in slides})
        for name, document in artifacts.items():
            (target / f"{name}.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "case_id": case["case_id"], "status": "pass", "pages": len(slides), "content_projection_drift": 0,
        "host_planning_pass_count": 1, "host_revision_pass_count": expected_revisions, "automatic_regeneration_count": 0,
        "planner_calls": 0, "reviewer_calls": 0, "approved_outline_sha256": canonical_sha256(approved),
        "slide_content_manifest_sha256": canonical_sha256(projection_manifest),
    }


def run_p05_regression(python_path: Path, node_path: Path) -> dict[str, Any]:
    command = [str(python_path), str(ROOT / "tools" / "runtime-eval" / "p05_runtime_eval.py"), "--tier", "Milestone", "--all", "--python-path", str(python_path), "--node-path", str(node_path)]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode:
        raise RuntimeError(completed.stderr or completed.stdout)
    return {"status": "pass", "command": "p05_runtime_eval Milestone --all", "agent_calls": 0}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="P1 content-planning deterministic evaluation")
    result.add_argument("--tier", choices=("Focused", "Milestone", "FinalGate"), default="Focused")
    result.add_argument("--case", choices=("D03", "D05", "D08"))
    result.add_argument("--all", action="store_true")
    result.add_argument("--work-root", type=Path, default=ROOT / "work" / "p1-content-planning")
    result.add_argument("--run-p05-regression", action="store_true")
    result.add_argument("--python-path", type=Path, default=Path(sys.executable))
    result.add_argument("--node-path", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    fixture = load_fixtures()
    selected = [args.case] if args.case else (["D03", "D05", "D08"] if args.all or args.tier in {"Milestone", "FinalGate"} else ["D03"])
    cases = {item["case_id"]: item for item in fixture["cases"]}
    try:
        results = [evaluate_case(cases[case_id], fixture["fixed_timestamp_utc"], args.work_root.resolve()) for case_id in selected]
        baseline = subprocess.run(["git", "diff", "--quiet", "ce815cc", "--", "baseline"], cwd=ROOT).returncode == 0
        if not baseline:
            raise RuntimeError("P0 baseline differs from ce815cc")
        p05 = None
        if args.run_p05_regression:
            if args.node_path is None:
                raise RuntimeError("--run-p05-regression requires --node-path")
            p05 = run_p05_regression(args.python_path.resolve(), args.node_path.resolve())
        report = {"status": "pass", "tier": args.tier, "cases": results, "p0_baseline_unchanged": baseline, "p05_regression": p05, "specialist_agent_calls": 0}
        args.work_root.mkdir(parents=True, exist_ok=True)
        (args.work_root / "p1-eval-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
