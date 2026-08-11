from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "content-to-editable-ppt" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from text_identity import build_compatibility_map, compatibility_view, compare_authority, layout_with_ppt_text
from agent_adapters import AgentCallLedger, TimeoutControllerAdapter, TimeoutTestAdapter
from reviewer_controller import run_reviewer_gate
from schema_utils import validate_schema


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="P0.5 deterministic Runtime evaluation")
    result.add_argument("--tier", choices=("Focused", "Milestone", "LiveSmoke", "FinalGate"), default="Focused")
    result.add_argument("--case", choices=tuple(f"B{i:02d}" for i in range(1, 7)))
    result.add_argument("--all", action="store_true")
    result.add_argument("--allow-live-agent", action="store_true")
    result.add_argument("--agent-call-budget", type=int, default=0)
    result.add_argument("--work-root", type=Path, default=ROOT / "work" / "p05-runtime-eval")
    result.add_argument("--python-path", type=Path, default=Path(sys.executable))
    result.add_argument("--node-path", type=Path)
    result.add_argument("--live-evidence", type=Path)
    return result


def _audit(case_id: str, output_root: Path) -> dict:
    case_root = ROOT / "baseline" / "cases" / case_id
    report = json.loads((case_root / "case-report.json").read_text(encoding="utf-8"))
    iteration = f"{report['final_iteration']:02d}"
    layout = json.loads((case_root / "evidence" / "iterations" / iteration / "layout.json").read_text(encoding="utf-8"))
    authority = json.loads((case_root / "evidence" / "baseline-source-content.json").read_text(encoding="utf-8"))
    mapping = build_compatibility_map(layout, authority)
    view = compatibility_view(layout, mapping, strict=False)
    extracted = layout_with_ppt_text(view, case_root / "evidence" / "final" / "baseline-final.pptx")
    comparison = compare_authority(authority, extracted)
    result = {"case_id": case_id, "mapping": mapping, "comparison": comparison, "agent_calls": 0}
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / f"{case_id}-text-identity-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _frozen_replay(case_id: str, output_root: Path, python_path: Path, node_path: Path | None) -> dict:
    audit = _audit(case_id, output_root / "audits")
    if case_id == "B01":
        if audit["comparison"]["missing"] != ["footer"]:
            raise RuntimeError("B01 must freeze the known missing footer as content_failure")
        return {"case_id": case_id, "status": "pass", "oracle": "content_failure", "agent_calls": 0}

    case_root = ROOT / "baseline" / "cases" / case_id
    report = json.loads((case_root / "case-report.json").read_text(encoding="utf-8"))
    frozen = case_root / "evidence" / "iterations" / f"{report['final_iteration']:02d}"
    work = output_root / "replays" / case_id
    if work.exists():
        shutil.rmtree(work)
    frozen_iteration = int(report["final_iteration"])
    iteration = work / "iterations" / f"{frozen_iteration:02d}"
    iteration.mkdir(parents=True)
    shutil.copy2(case_root / "input" / "request.json", work / "request.json")
    shutil.copy2(case_root / "input" / "source.png", work / "source.png")
    for name in ("layout.json", "crops.json", "asset_manifest.json"):
        shutil.copy2(frozen / name, iteration / name)
    frozen_assets = case_root / "evidence" / "final" / "assets"
    if frozen_assets.is_dir():
        (iteration / "assets").mkdir()
        for asset in frozen_assets.iterdir():
            if asset.is_file():
                shutil.copy2(asset, iteration / "assets" / asset.name)
    command = [
        str(python_path), str(SCRIPT_DIR / "run_pipeline.py"),
        "--request", str(work / "request.json"),
        "--iteration-dir", str(iteration),
        "--output-ppt", str(iteration / "replay.pptx"),
        "--execution-mode", "diagnostic",
        "--renderer", "powerpoint",
        "--run-id", f"p05-replay-{case_id}",
        "--iteration", str(frozen_iteration),
        "--log-file", str(iteration / "pipeline.log"),
    ]
    if node_path:
        command.extend(["--node", str(node_path)])
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    result = {
        "case_id": case_id,
        "status": "pass" if completed.returncode == 0 else "fail",
        "oracle": "build_render_qa",
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip().splitlines()[-1:] or [],
        "stderr": completed.stderr.strip().splitlines()[-3:] or [],
        "agent_calls": 0,
    }
    if completed.returncode == 0 and case_id == "B06":
        stage_state = json.loads((iteration / "stage_state.json").read_text(encoding="utf-8"))
        for stage_name in ("asset_processing", "asset_crop", "svg_sanitize"):
            if stage_state["stages"].get(stage_name, {}).get("status") != "skipped":
                raise RuntimeError(f"B06 {stage_name} was not skipped")
        if stage_state["counters"]["technical_retries"] != 0:
            raise RuntimeError("B06 used a technical retry")
    (output_root / "replays").mkdir(parents=True, exist_ok=True)
    (output_root / "replays" / f"{case_id}-replay-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _b01_corrected_replay(output_root: Path, python_path: Path, node_path: Path | None) -> dict:
    case_root = ROOT / "baseline" / "cases" / "B01"
    case_report = json.loads((case_root / "case-report.json").read_text(encoding="utf-8"))
    frozen = case_root / "evidence" / "iterations" / f"{case_report['final_iteration']:02d}"
    authority = json.loads((case_root / "evidence" / "baseline-source-content.json").read_text(encoding="utf-8"))
    authority = json.loads(json.dumps(authority))
    authority["artifact_role"] = "p05_corrected_fixture"
    authority["runtime_contract"] = True
    authority["text_items"].extend([
        {"id": "badge-1", "text": "1"},
        {"id": "badge-2", "text": "2"},
        {"id": "badge-3", "text": "3"},
    ])
    layout = json.loads((frozen / "layout.json").read_text(encoding="utf-8"))
    mapping = build_compatibility_map(layout, authority, explicit={
        "footer": [{"element_id": "footer_text", "segment_order": 0, "joiner": ""}],
        "badge-1": [{"element_id": "badge_text_01", "segment_order": 0, "joiner": ""}],
        "badge-2": [{"element_id": "badge_text_02", "segment_order": 0, "joiner": ""}],
        "badge-3": [{"element_id": "badge_text_03", "segment_order": 0, "joiner": ""}],
    })
    corrected = compatibility_view(layout, mapping)
    footer_text = next(item for item in authority["text_items"] if item["id"] == "footer")["text"]
    next(item for item in corrected["elements"] if item["id"] == "footer_text")["text"] = footer_text
    if compare_authority(authority, corrected)["status"] != "pass":
        raise RuntimeError("B01 corrected fixture does not satisfy canonical authority")

    work = output_root / "corrected" / "B01"
    if work.exists():
        shutil.rmtree(work)
    iteration = work / "iterations" / "03"
    iteration.mkdir(parents=True)
    shutil.copy2(case_root / "input" / "request.json", work / "request.json")
    shutil.copy2(case_root / "input" / "source.png", work / "source.png")
    (work / "source-content.json").write_text(json.dumps(authority, ensure_ascii=False, indent=2), encoding="utf-8")
    (iteration / "layout.json").write_text(json.dumps(corrected, ensure_ascii=False, indent=2), encoding="utf-8")
    for name in ("crops.json", "asset_manifest.json"):
        shutil.copy2(frozen / name, iteration / name)
    command = [
        str(python_path), str(SCRIPT_DIR / "run_pipeline.py"),
        "--request", str(work / "request.json"), "--iteration-dir", str(iteration),
        "--output-ppt", str(iteration / "corrected.pptx"), "--execution-mode", "diagnostic",
        "--renderer", "powerpoint", "--run-id", "p05-b01-corrected", "--iteration", "3",
        "--log-file", str(iteration / "pipeline.log"),
    ]
    if node_path:
        command.extend(["--node", str(node_path)])
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"B01 corrected fixture pipeline failed: {completed.stderr or completed.stdout}")
    extracted = layout_with_ppt_text(corrected, iteration / "corrected.pptx")
    content = compare_authority(authority, extracted)
    if content["status"] != "pass":
        raise RuntimeError(f"B01 corrected PPT content failed: {content}")
    return {"case_id": "B01", "status": "pass", "oracle": "corrected_build_render_qa_content", "agent_calls": 0}


def _timeout_integration() -> dict:
    ledger = AgentCallLedger()
    result = run_reviewer_gate(
        TimeoutControllerAdapter(TimeoutTestAdapter(sleep_seconds=6), timeout_seconds=5),
        ledger=ledger, task_id="p05-timeout", iteration=1, call_id="timeout-reviewer",
        structural_pass=True, content_pass=True, editability_pass=True,
    )
    if result["status"] != "delivered_with_warnings" or result["attempt_count"] != 3 or result["technical_retry_count"] != 2:
        raise RuntimeError("timeout controller did not exhaust Initial + 2 Retry into delivered_with_warnings")
    if ledger.live_call_count != 0 or any(item["role"] != "reviewer" for item in ledger.calls):
        raise RuntimeError("timeout fixture consumed live budget or invoked a non-Reviewer role")
    return {"status": "pass", "attempts": 3, "technical_retries": 2, "live_agent_calls": 0, "planner_calls": 0}


def _validate_live_evidence(path: Path, budget: int) -> dict:
    if not path.is_file():
        raise RuntimeError(f"Final Gate live evidence is missing: {path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("mode") != "single_pass" or report.get("max_total_iterations") != 1 or report.get("max_visual_revisions") != 0:
        raise RuntimeError("live evidence is not Single-Pass Contract Mode")
    calls = report.get("agent_calls", {})
    if calls.get("planner") != 6 or calls.get("reviewer") != 6 or calls.get("total") != 12 or calls["total"] > budget:
        raise RuntimeError("live Agent call counts do not match the Final Gate budget")
    cases = report.get("cases", [])
    if [item.get("case_id") for item in cases] != [f"B{i:02d}" for i in range(1, 7)]:
        raise RuntimeError("live evidence must contain B01-B06 in order")
    if any(item.get("planner_calls") != 1 or item.get("reviewer_calls") != 1 or item.get("visual_revisions") != 0 for item in cases):
        raise RuntimeError("a live case exceeded its single-pass call limit")
    for item in cases:
        attribution = item.get("issue_attribution", {})
        if item.get("highest_severity") in {"major", "critical"} and not attribution:
            raise RuntimeError(f"{item.get('case_id')} lacks Major/Critical attribution")
        if attribution:
            validate_schema("issue_attribution", attribution, ROOT / "content-to-editable-ppt" / "schemas")
        if attribution.get("classification") == "runtime_regression":
            raise RuntimeError(f"{item.get('case_id')} has a deterministic runtime regression")
    return report


def main() -> int:
    args = parser().parse_args()
    if args.tier in {"LiveSmoke", "FinalGate"}:
        if not args.allow_live_agent or args.agent_call_budget <= 0:
            raise SystemExit("live tiers require --allow-live-agent and a positive --agent-call-budget")
        if args.tier == "LiveSmoke":
            raise SystemExit("Live Smoke packages are executed by the Host in a fresh Agent context")
    if args.tier not in {"LiveSmoke", "FinalGate"} and (args.allow_live_agent or args.agent_call_budget):
        raise SystemExit("deterministic tiers reject live Agent authorization")

    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests" / "runtime"), "-p", "test_*.py"], cwd=ROOT)
    if tests.returncode:
        return tests.returncode
    cases = [args.case] if args.case else ([f"B{i:02d}" for i in range(1, 7)] if args.all or args.tier in {"Milestone", "FinalGate"} else ["B01"])
    if args.tier in {"Milestone", "FinalGate"}:
        results = [_frozen_replay(case_id, args.work_root, args.python_path, args.node_path) for case_id in cases]
        failed = [item for item in results if item["status"] != "pass"]
        if failed:
            print(json.dumps(failed[0], ensure_ascii=False, indent=2))
            return 1
        corrected = _b01_corrected_replay(args.work_root, args.python_path, args.node_path) if args.tier == "FinalGate" else None
        if args.tier == "FinalGate":
            live = _validate_live_evidence(args.live_evidence or args.work_root / "final-live-report.json", args.agent_call_budget)
            timeout = _timeout_integration()
            print(json.dumps({"status": "pass", "tier": args.tier, "cases": cases, "corrected": corrected, "timeout": timeout, "agent_calls": live["agent_calls"]}, ensure_ascii=False))
            return 0
        print(json.dumps({"status": "pass", "tier": args.tier, "cases": cases, "agent_calls": 0}, ensure_ascii=False))
        return 0

    results = [_audit(case_id, args.work_root) for case_id in cases]
    expected = {"B01": "fail"}
    for result in results:
        wanted = expected.get(result["case_id"], "pass")
        if result["comparison"]["status"] != wanted:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1
    print(json.dumps({"status": "pass", "tier": args.tier, "cases": cases, "agent_calls": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
