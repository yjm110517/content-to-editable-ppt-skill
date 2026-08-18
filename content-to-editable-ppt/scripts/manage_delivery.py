from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from canonical_artifact import canonical_sha256
from delivery_authority import load_delivery_authority
from delivery_state import initial_delivery_state, transition
from final_integrity import verify_final_integrity
from deck_qa import run_deck_qa
from schema_utils import ContractError, error, load_json, validate_schema

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")


def _load_state(path: Path) -> dict:
    state = load_json(path)
    validate_schema("deck_delivery_state", state, SCHEMA_DIR)
    return state


def _save_state(path: Path, state: dict) -> None:
    validate_schema("deck_delivery_state", state, SCHEMA_DIR)
    _write_json(path, state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage deterministic P5 final integrity, deck review, and immutable delivery.")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init")
    init.add_argument("--state", type=Path, required=True)
    init.add_argument("--p4-state", type=Path, required=True)
    init.add_argument("--p4-manifest", type=Path, required=True)
    init.add_argument("--p4-candidate-report", type=Path, required=True)
    init.add_argument("--p4-drift-report", type=Path, required=True)
    init.add_argument("--p4-render-report", type=Path, required=True)
    init.add_argument("--candidate-pptx", type=Path, required=True)

    integrity = commands.add_parser("verify-final-integrity")
    integrity.add_argument("--state", type=Path, required=True)
    integrity.add_argument("--p4-state", type=Path, required=True)
    integrity.add_argument("--p4-manifest", type=Path, required=True)
    integrity.add_argument("--p4-candidate-report", type=Path, required=True)
    integrity.add_argument("--p4-drift-report", type=Path, required=True)
    integrity.add_argument("--p4-render-report", type=Path, required=True)
    integrity.add_argument("--candidate-pptx", type=Path, required=True)
    integrity.add_argument("--p4-render-root", type=Path, required=True)
    integrity.add_argument("--render-dir", type=Path, required=True)
    integrity.add_argument("--render-report", type=Path, required=True)
    integrity.add_argument("--output", type=Path, required=True)
    integrity.add_argument("--width-px", type=int, required=True)
    integrity.add_argument("--height-px", type=int, required=True)
    integrity.add_argument("--timeout-seconds", type=int, default=180)

    qa = commands.add_parser("run-deck-qa")
    qa.add_argument("--state", type=Path, required=True)
    qa.add_argument("--p4-state", type=Path, required=True)
    qa.add_argument("--p4-manifest", type=Path, required=True)
    qa.add_argument("--p4-candidate-report", type=Path, required=True)
    qa.add_argument("--p4-drift-report", type=Path, required=True)
    qa.add_argument("--candidate-pptx", type=Path, required=True)
    qa.add_argument("--output", type=Path, required=True)

    roundtrip = commands.add_parser("run-roundtrip")
    roundtrip.add_argument("--state", type=Path, required=True)
    roundtrip.add_argument("--candidate-pptx", type=Path, required=True)
    roundtrip.add_argument("--p4-manifest", type=Path, required=True)
    roundtrip.add_argument("--output", type=Path, required=True)
    roundtrip.add_argument("--width-px", type=int, required=True)
    roundtrip.add_argument("--height-px", type=int, required=True)
    roundtrip.add_argument("--timeout-seconds", type=int, default=240)

    verify = commands.add_parser("verify")
    verify.add_argument("--state", type=Path, required=True)
    return parser


def _bundle(args: argparse.Namespace) -> dict:
    return load_delivery_authority(
        p4_state_path=args.p4_state,
        p4_manifest_path=args.p4_manifest,
        p4_candidate_report_path=args.p4_candidate_report,
        p4_drift_report_path=args.p4_drift_report,
        p4_render_report_path=args.p4_render_report,
        p4_candidate_pptx=args.candidate_pptx,
    )


def run(args: argparse.Namespace) -> dict:
    if args.command == "init":
        bundle = _bundle(args)
        state_path = args.state.resolve()
        if state_path.exists():
            raise ContractError([error("$.state", "delivery state already exists", "output_conflict")])
        state = initial_delivery_state(bundle["deck_id"], bundle["p4_state_sha256"])
        state = transition(state, "p5_preflight", artifact_updates={"p4_state_sha256": bundle["p4_state_sha256"], "candidate_deck_sha256": bundle["p4_candidate_pptx_sha256"], "manifest_compatibility": bundle["manifest_compatibility"]})
        _save_state(state_path, state)
        return {"state": str(state_path), "deck_id": bundle["deck_id"], "state_name": state["state"], "manifest_compatibility": bundle["manifest_compatibility"]}
    if args.command == "verify-final-integrity":
        state = _load_state(args.state)
        bundle = _bundle(args)
        manifest = verify_final_integrity(
            bundle=bundle,
            candidate_pptx=args.candidate_pptx,
            p4_render_root=args.p4_render_root,
            p5_render_dir=args.render_dir,
            p5_render_report_path=args.render_report,
            width_px=args.width_px,
            height_px=args.height_px,
            timeout_seconds=args.timeout_seconds,
        )
        _write_json(args.output, manifest)
        updated = transition(state, "final_integrity_check", artifact_updates={"p5_final_render_manifest_sha256": canonical_sha256(manifest)})
        _save_state(args.state, updated)
        return {"manifest": str(args.output.resolve()), "status": "pass", "p4_fidelity_inherited": True}
    if args.command == "run-deck-qa":
        state = _load_state(args.state)
        report = run_deck_qa(
            deck_id=state["deck_id"],
            candidate_pptx=args.candidate_pptx,
            p4_state=load_json(args.p4_state),
            p4_manifest=load_json(args.p4_manifest),
            p4_candidate_report=load_json(args.p4_candidate_report),
            p4_drift_report=load_json(args.p4_drift_report),
        )
        _write_json(args.output, report)
        if report["status"] != "pass":
            raise ContractError([error("$.qa_report", "deck final QA failed", "deck_qa_failed")])
        updated = transition(state, "deterministic_deck_qa", artifact_updates={"deck_final_qa_report_sha256": canonical_sha256(report), "exception_pages": report["exception_pages"]})
        _save_state(args.state, updated)
        return {"qa_report": str(args.output.resolve()), "status": "pass", "exception_pages": report["exception_pages"]}
    if args.command == "run-roundtrip":
        state = _load_state(args.state)
        command = [sys.executable, str(Path(__file__).with_name("deck_roundtrip.py")), "--deck-id", state["deck_id"], "--candidate-pptx", str(args.candidate_pptx), "--p4-manifest", str(args.p4_manifest), "--output", str(args.output), "--width-px", str(args.width_px), "--height-px", str(args.height_px), "--timeout-seconds", str(args.timeout_seconds)]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if completed.returncode:
            raise ContractError([error("$.run_roundtrip", completed.stdout.strip() or completed.stderr.strip(), "roundtrip_failed")])
        report = load_json(args.output)
        updated = transition(state, "roundtrip_check", artifact_updates={"powerpoint_roundtrip_report_sha256": canonical_sha256(report)})
        _save_state(args.state, updated)
        return {"roundtrip_report": str(args.output.resolve()), "status": "pass"}
    if args.command == "verify":
        state = _load_state(args.state)
        failures: list[dict] = []
        if state["state"] not in {"delivered", "live_review_pending"}:
            failures.append(error("$.state", "P5 delivery state is not at a valid verification point", "invalid_state"))
        if failures:
            raise ContractError(failures)
        return {"deck_id": state["deck_id"], "state": state["state"], "delivery_artifacts": state["current_artifacts"]}
    raise AssertionError(args.command)


def main() -> int:
    try:
        args = build_parser().parse_args()
        outputs = run(args)
        print(json.dumps({"status": "ok", "outputs": outputs, "error": None}, ensure_ascii=False))
        return 0
    except Exception as exc:
        issues = exc.errors if isinstance(exc, ContractError) else [{"path": "$", "code": "p5_internal_error", "message": str(exc)}]
        print(json.dumps({"status": "error", "outputs": {}, "error": {"issues": issues}}, ensure_ascii=False))
        return 4 if isinstance(exc, ContractError) else 70


if __name__ == "__main__":
    raise SystemExit(main())
