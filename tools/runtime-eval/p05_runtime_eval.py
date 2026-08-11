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


def main() -> int:
    args = parser().parse_args()
    if args.tier in {"LiveSmoke", "FinalGate"}:
        if not args.allow_live_agent or args.agent_call_budget <= 0:
            raise SystemExit("live tiers require --allow-live-agent and a positive --agent-call-budget")
        raise SystemExit("live Agent transport is intentionally unavailable in PR1")
    if args.allow_live_agent or args.agent_call_budget:
        raise SystemExit("deterministic tiers reject live Agent authorization")

    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests" / "runtime"), "-p", "test_*.py"], cwd=ROOT)
    if tests.returncode:
        return tests.returncode
    cases = [args.case] if args.case else ([f"B{i:02d}" for i in range(1, 7)] if args.all or args.tier == "Milestone" else ["B01"])
    if args.tier == "Milestone":
        results = [_frozen_replay(case_id, args.work_root, args.python_path, args.node_path) for case_id in cases]
        failed = [item for item in results if item["status"] != "pass"]
        if failed:
            print(json.dumps(failed[0], ensure_ascii=False, indent=2))
            return 1
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
