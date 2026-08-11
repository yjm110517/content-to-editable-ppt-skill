from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
BASELINE = ROOT / "baseline" / "cases"
DEFAULT_WORK = ROOT / "work" / "p05-runtime-eval" / "final-live"


class HostError(RuntimeError):
    pass


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Host-side P0.5 Single-Pass Live E2E orchestration")
    result.add_argument("--action", choices=("Prepare", "FinalizePlanner", "RunRuntime", "PrepareFrozenReviewer", "ValidateFrozenReviewer", "FinalizeReviewer", "Report"), required=True)
    result.add_argument("--case", choices=tuple(f"B{i:02d}" for i in range(1, 7)))
    result.add_argument("--all", action="store_true")
    result.add_argument("--work-root", type=Path, default=DEFAULT_WORK)
    result.add_argument("--python-path", type=Path, default=Path(sys.executable))
    result.add_argument("--node-path", type=Path)
    return result


def _run(command: list[str]) -> dict:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise HostError(f"invalid CLI output: {completed.stderr or completed.stdout}") from exc
    if completed.returncode != 0 or payload.get("status") != "ok":
        raise HostError(json.dumps(payload.get("error") or payload, ensure_ascii=False))
    return payload


def _paths(root: Path, case_id: str) -> dict[str, Path | str]:
    work = root / case_id
    call_id = f"planner-{case_id.lower()}-p05-final"
    reviewer_id = f"reviewer-{case_id.lower()}-p05-final"
    iteration = work / "iterations" / "01"
    return {
        "work": work, "iteration": iteration, "log": work / "p05-live.log",
        "planner_id": call_id, "planner": work / ".agent-calls" / "01" / "planner" / call_id,
        "reviewer_id": reviewer_id, "reviewer": work / ".agent-calls" / "01" / "reviewer" / reviewer_id,
    }


def prepare(case_id: str, root: Path, python: Path) -> dict:
    paths = _paths(root, case_id)
    work = paths["work"]
    if work.exists():
        raise HostError(f"live work root already exists: {work}")
    work.mkdir(parents=True)
    case = BASELINE / case_id
    request = json.loads((case / "input" / "request.json").read_text(encoding="utf-8"))
    request["task_id"] = f"p05-live-{case_id.lower()}"
    request["review_policy"]["max_iterations"] = 1
    (work / "request.json").write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(case / "input" / "source.png", work / "source.png")
    shutil.copy2(case / "evidence" / "baseline-source-content.json", work / "source-content.json")
    run_id = request["task_id"]
    common = ["--run-id", run_id, "--log-file", str(paths["log"])]
    _run([str(python), str(SCRIPTS / "manage_run_state.py"), "init", "--work-root", str(work), "--request", str(work / "request.json"), "--output", str(work / "run_state.json"), *common])
    _run([str(python), str(SCRIPTS / "manage_run_state.py"), "advance", "--work-root", str(work), "--state", str(work / "run_state.json"), "--event", "inputs_resolved", *common])
    payload = _run([
        str(python), str(SCRIPTS / "prepare_agent_call.py"), "--role", "planner", "--mode", "initial",
        "--work-root", str(work), "--request", str(work / "request.json"), "--source", str(work / "source.png"),
        "--content-authority", str(work / "source-content.json"), "--iteration", "1", "--call-id", str(paths["planner_id"]),
        "--output-dir", str(paths["planner"]), *common,
    ])
    return {"case_id": case_id, "call_dir": payload["outputs"]["call_dir"]}


def finalize_planner(case_id: str, root: Path, python: Path) -> dict:
    paths = _paths(root, case_id)
    work, iteration = paths["work"], paths["iteration"]
    run_id = f"p05-live-{case_id.lower()}"
    common = ["--run-id", run_id, "--log-file", str(paths["log"])]
    _run([str(python), str(SCRIPTS / "finalize_agent_response.py"), "--role", "planner", "--mode", "initial", "--call-dir", str(paths["planner"]), "--output-dir", str(iteration), "--iteration", "1", *common])
    for event in ("spec_validated", "build_started"):
        _run([str(python), str(SCRIPTS / "manage_run_state.py"), "advance", "--work-root", str(work), "--state", str(work / "run_state.json"), "--event", event, *common])
    return {"case_id": case_id, "status": "planner_finalized"}


def run_runtime(case_id: str, root: Path, python: Path, node: Path) -> dict:
    paths = _paths(root, case_id)
    work, iteration = paths["work"], paths["iteration"]
    run_id = f"p05-live-{case_id.lower()}"
    _run([
        str(python), str(SCRIPTS / "run_pipeline.py"), "--request", str(work / "request.json"),
        "--iteration-dir", str(iteration), "--output-ppt", str(iteration / "live.pptx"),
        "--execution-mode", "production", "--run-state", str(work / "run_state.json"),
        "--renderer", "powerpoint", "--node", str(node), "--run-id", run_id, "--iteration", "1",
        "--log-file", str(iteration / "pipeline.log"),
    ])
    _run([
        str(python), str(SCRIPTS / "validate_content_authority.py"), "--authority", str(work / "source-content.json"),
        "--layout", str(iteration / "layout.json"), "--ppt", str(iteration / "live.pptx"),
        "--output", str(iteration / "content_authority_report.json"), "--run-id", run_id,
    ])
    prepared = _run([
        str(python), str(SCRIPTS / "run_review_checkpoint.py"), "--work-root", str(work),
        "--iteration-dir", str(iteration), "--run-state", str(work / "run_state.json"),
        "--planner-call-record", str(paths["planner"] / "call_record.json"), "--call-id", str(paths["reviewer_id"]),
        "--run-id", run_id, "--iteration", "1", "--log-file", str(paths["log"]),
    ])
    return {"case_id": case_id, "status": "runtime_pass", "reviewer_call_dir": prepared["outputs"]["call_dir"]}


def finalize_reviewer(case_id: str, root: Path, python: Path) -> dict:
    paths = _paths(root, case_id)
    work, iteration = paths["work"], paths["iteration"]
    run_id = f"p05-live-{case_id.lower()}"
    common = ["--run-id", run_id, "--iteration", "1", "--log-file", str(paths["log"])]
    _run([
        str(python), str(SCRIPTS / "finalize_agent_response.py"), "--role", "reviewer", "--mode", "review",
        "--call-dir", str(paths["reviewer"]), "--planner-call-record", str(paths["planner"] / "call_record.json"),
        "--iteration-dir", str(iteration), "--output", str(iteration / "review_report.json"), *common,
    ])
    _run([str(python), str(SCRIPTS / "manage_run_state.py"), "advance", "--work-root", str(work), "--state", str(work / "run_state.json"), "--event", "review_ready", "--artifact", str(iteration / "review_report.json"), "--run-id", run_id, "--log-file", str(paths["log"])])
    _run([
        str(python), str(SCRIPTS / "evaluate_review.py"), "--request", str(work / "request.json"),
        "--qa-report", str(iteration / "qa_report.json"), "--review-report", str(iteration / "review_report.json"),
        "--output", str(iteration / "review_evaluation.json"), *common,
    ])
    _run([str(python), str(SCRIPTS / "manage_run_state.py"), "advance", "--work-root", str(work), "--state", str(work / "run_state.json"), "--event", "evaluation_result", "--artifact", str(iteration / "review_evaluation.json"), "--run-id", run_id, "--log-file", str(paths["log"])])
    evaluation = json.loads((iteration / "review_evaluation.json").read_text(encoding="utf-8"))
    state = json.loads((work / "run_state.json").read_text(encoding="utf-8"))
    (work / "case-result.json").write_text(json.dumps({"case_id": case_id, "planner_status": "accepted", "runtime_status": "pass", "reviewer_recommendation": json.loads((iteration / "review_report.json").read_text(encoding="utf-8"))["reviewer_recommendation"], "policy_decision": evaluation["policy_decision"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"case_id": case_id, "status": "reviewer_finalized", "policy_decision": evaluation["policy_decision"], "run_state": state["state"]}


def _frozen_reviewer_paths(root: Path, case_id: str) -> tuple[Path, Path]:
    work = root.parent / "final-frozen-review" / case_id
    call_id = f"reviewer-{case_id.lower()}-p05-final"
    return work, work / ".agent-calls" / "01" / "reviewer" / call_id


def prepare_frozen_reviewer(case_id: str, root: Path, python: Path) -> dict:
    work, call = _frozen_reviewer_paths(root, case_id)
    if work.exists():
        raise HostError(f"frozen Reviewer work root already exists: {work}")
    case = BASELINE / case_id
    report_doc = json.loads((case / "case-report.json").read_text(encoding="utf-8"))
    frozen = case / "evidence" / "iterations" / f"{report_doc['final_iteration']:02d}"
    iteration = work / "iterations" / "01"
    iteration.mkdir(parents=True)
    request = json.loads((case / "input" / "request.json").read_text(encoding="utf-8"))
    request["task_id"] = f"p05-live-review-{case_id.lower()}"
    (work / "request.json").write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(case / "input" / "source.png", work / "source.png")
    for source_name, target_name in (("layout.json", "layout.json"), ("qa_report.json", "qa_report.json"), ("asset_manifest.json", "asset_manifest.json"), ("rendered_slide.png", "rendered_slide.png")):
        document_source = frozen / source_name
        if source_name in {"layout.json", "qa_report.json"}:
            document = json.loads(document_source.read_text(encoding="utf-8"))
            if source_name == "layout.json":
                document["metadata"]["iteration"] = 1
            else:
                document["task_id"] = request["task_id"]
                document["iteration"] = 1
            (iteration / target_name).write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            shutil.copy2(document_source, iteration / target_name)
    call_id = f"reviewer-{case_id.lower()}-p05-final"
    payload = _run([
        str(python), str(SCRIPTS / "prepare_agent_call.py"), "--role", "reviewer", "--mode", "review",
        "--work-root", str(work), "--request", str(work / "request.json"), "--source", str(work / "source.png"),
        "--render", str(iteration / "rendered_slide.png"), "--layout", str(iteration / "layout.json"),
        "--qa-report", str(iteration / "qa_report.json"), "--asset-manifest", str(iteration / "asset_manifest.json"),
        "--iteration", "1", "--call-id", call_id, "--output-dir", str(call), "--run-id", request["task_id"],
    ])
    return {"case_id": case_id, "call_dir": payload["outputs"]["call_dir"]}


def validate_frozen_reviewer(case_id: str, root: Path) -> dict:
    work, call = _frozen_reviewer_paths(root, case_id)
    sys.path.insert(0, str(SCRIPTS))
    from agent_common import load_call_bundle
    from reviewer_controller import route_reviewer_response
    _, _, response, _ = load_call_bundle(call, work_root=work, role="reviewer", mode="review")
    route = route_reviewer_response(response)
    result = {"case_id": case_id, "planner_status": "classified_rejection", "runtime_status": "not_started", "reviewer_recommendation": response["reviewer_recommendation"], "policy_decision": route}
    (_paths(root, case_id)["work"] / "case-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def report(root: Path) -> dict:
    sys.path.insert(0, str(SCRIPTS))
    from issue_attribution import EVIDENCE_KEYS, attribute_issue

    cases = []
    for case_id in (f"B{i:02d}" for i in range(1, 7)):
        paths = _paths(root, case_id)
        iteration = paths["iteration"]
        result = json.loads((paths["work"] / "case-result.json").read_text(encoding="utf-8"))
        if (iteration / "review_report.json").is_file():
            review = json.loads((iteration / "review_report.json").read_text(encoding="utf-8"))
        else:
            _, call = _frozen_reviewer_paths(root, case_id)
            review = json.loads((call / "raw_response.json").read_text(encoding="utf-8"))
        highest = next((severity for severity in ("critical", "major", "minor", "suggestion") if any(item["severity"] == severity for item in review["issues"])), "none")
        attribution = attribute_issue(
            case_id=case_id,
            reviewer_severity=highest,
            deterministic_evidence={key: False for key in EVIDENCE_KEYS},
            # Rejected Planner candidates use the frozen P0 render, so any
            # visual finding is demonstrably present in the frozen evidence.
            pre_existing_visual_issue=(
                result["planner_status"] == "classified_rejection" and highest != "none"
            ),
        )
        attribution_path = paths["work"] / "issue-attribution.json"
        attribution_path.write_text(json.dumps(attribution, ensure_ascii=False, indent=2), encoding="utf-8")
        cases.append({
            "case_id": case_id, "planner_calls": 1, "reviewer_calls": 1, "visual_revisions": 0,
            "planner_status": result["planner_status"], "runtime_status": result["runtime_status"], "reviewer_recommendation": review["reviewer_recommendation"],
            "policy_decision": result["policy_decision"], "highest_severity": highest,
            "issue_attribution": attribution,
        })
    document = {
        "schema_version": "1.0", "mode": "single_pass", "max_total_iterations": 1, "max_visual_revisions": 0,
        "agent_calls": {"planner": 6, "reviewer": 6, "total": 12}, "cases": cases,
    }
    target = root.parent / "final-live-report.json"
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"report": str(target), **document}


def main() -> int:
    args = parser().parse_args()
    root = args.work_root.resolve()
    cases = [args.case] if args.case else ([f"B{i:02d}" for i in range(1, 7)] if args.all else [])
    if args.action != "Report" and not cases:
        raise SystemExit("--case or --all is required")
    try:
        if args.action == "Prepare":
            output = [prepare(case_id, root, args.python_path.resolve()) for case_id in cases]
        elif args.action == "FinalizePlanner":
            output = [finalize_planner(case_id, root, args.python_path.resolve()) for case_id in cases]
        elif args.action == "RunRuntime":
            if args.node_path is None:
                raise HostError("RunRuntime requires --node-path")
            output = [run_runtime(case_id, root, args.python_path.resolve(), args.node_path.resolve()) for case_id in cases]
        elif args.action == "PrepareFrozenReviewer":
            output = [prepare_frozen_reviewer(case_id, root, args.python_path.resolve()) for case_id in cases]
        elif args.action == "ValidateFrozenReviewer":
            output = [validate_frozen_reviewer(case_id, root) for case_id in cases]
        elif args.action == "FinalizeReviewer":
            output = [finalize_reviewer(case_id, root, args.python_path.resolve()) for case_id in cases]
        else:
            output = report(root)
        print(json.dumps({"status": "ok", "outputs": output}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
