from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "content-to-editable-ppt" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from text_identity import build_compatibility_map, compatibility_view, compare_authority


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="P0.5 deterministic Runtime evaluation")
    result.add_argument("--tier", choices=("Focused", "Milestone", "LiveSmoke", "FinalGate"), default="Focused")
    result.add_argument("--case", choices=tuple(f"B{i:02d}" for i in range(1, 7)))
    result.add_argument("--all", action="store_true")
    result.add_argument("--allow-live-agent", action="store_true")
    result.add_argument("--agent-call-budget", type=int, default=0)
    result.add_argument("--work-root", type=Path, default=ROOT / "work" / "p05-runtime-eval")
    return result


def _audit(case_id: str, output_root: Path) -> dict:
    case_root = ROOT / "baseline" / "cases" / case_id
    report = json.loads((case_root / "case-report.json").read_text(encoding="utf-8"))
    iteration = f"{report['final_iteration']:02d}"
    layout = json.loads((case_root / "evidence" / "iterations" / iteration / "layout.json").read_text(encoding="utf-8"))
    authority = json.loads((case_root / "evidence" / "baseline-source-content.json").read_text(encoding="utf-8"))
    mapping = build_compatibility_map(layout, authority)
    view = compatibility_view(layout, mapping, strict=False)
    comparison = compare_authority(authority, view)
    result = {"case_id": case_id, "mapping": mapping, "comparison": comparison, "agent_calls": 0}
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / f"{case_id}-text-identity-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
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
