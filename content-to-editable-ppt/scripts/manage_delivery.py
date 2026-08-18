from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from canonical_artifact import canonical_sha256
from delivery_authority import file_sha256, load_delivery_authority
from delivery_state import initial_delivery_state, transition
from final_integrity import verify_final_integrity
from deck_qa import run_deck_qa
from p5_atomic import atomic_replace_p5_state, write_once_p5_artifact
from packaging_runtime import build_package_candidate, lock_packaging_runtime, package_formal_delivery, verify_delivery
from schema_utils import ContractError, error, load_json, validate_schema

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def _normalize_user_message(raw: bytes) -> str:
    """Unicode NFC + CRLF/CR -> LF; other whitespace preserved."""
    text = raw.decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")


def _load_state(path: Path) -> dict:
    state = load_json(path)
    validate_schema("deck_delivery_state", state, SCHEMA_DIR)
    return state


def _save_state(path: Path, state: dict) -> None:
    validate_schema("deck_delivery_state", state, SCHEMA_DIR)
    atomic_replace_p5_state(path, state)


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

    warning = commands.add_parser("record-warning-response")
    warning.add_argument("--state", type=Path, required=True)
    warning.add_argument("--qa-report", type=Path, required=True)
    warning.add_argument("--deck-consistency-report", type=Path, required=True)
    warning.add_argument("--evaluation", type=Path, required=True)
    warning.add_argument("--user-message", type=Path, required=True)
    warning.add_argument("--decision", choices=("accept", "reject"), required=True)
    warning.add_argument("--output", type=Path, required=True)

    decision = commands.add_parser("create-decision")
    decision.add_argument("--state", type=Path, required=True)
    decision.add_argument("--candidate-pptx", type=Path, required=True)
    decision.add_argument("--qa-report", type=Path, required=True)
    decision.add_argument("--roundtrip-report", type=Path, required=True)
    decision.add_argument("--deck-consistency-report", type=Path, required=True)
    decision.add_argument("--evaluation", type=Path, required=True)
    decision.add_argument("--p4-candidate-report", type=Path, required=True)
    decision.add_argument("--exception-review-record", action="append")
    decision.add_argument("--warning-acceptance", type=Path)
    decision.add_argument("--output", type=Path, required=True)

    lock = commands.add_parser("lock-packaging-runtime")
    lock.add_argument("--state", type=Path, required=True)
    lock.add_argument("--output", type=Path, required=True)

    package = commands.add_parser("package")
    package.add_argument("--state", type=Path, required=True)
    package.add_argument("--mode", choices=("candidate", "formal"), required=True)
    package.add_argument("--output-name", required=True)
    package.add_argument("--candidate-pptx", type=Path, required=True)
    package.add_argument("--work-root", type=Path)
    package.add_argument("--dist-root", type=Path)
    package.add_argument("--runtime-lock", type=Path, required=True)
    package.add_argument("--qa-report", type=Path, required=True)
    package.add_argument("--deck-consistency-report", type=Path)
    package.add_argument("--roundtrip-report", type=Path, required=True)
    package.add_argument("--decision", type=Path)
    package.add_argument("--final-render-manifest", type=Path, required=True)
    package.add_argument("--contact-sheets-dir", type=Path, required=True)
    package.add_argument("--final-renders-dir", type=Path, required=True)
    package.add_argument("--p4-asset-manifest", type=Path, required=True)
    package.add_argument("--p4-evidence-root", type=Path, required=True)

    verify = commands.add_parser("verify")
    verify.add_argument("--state", type=Path, required=True)
    verify.add_argument("--delivery-dir", type=Path)
    verify.add_argument("--dist-root", type=Path)
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
    if args.command == "record-warning-response":
        state = _load_state(args.state)
        qa_report = load_json(args.qa_report)
        report = load_json(args.deck_consistency_report)
        evaluation = load_json(args.evaluation)
        normalized = _normalize_user_message(args.user_message.read_bytes())
        acceptance = {
            "schema_version": "1.0",
            "artifact_type": "warning_acceptance",
            "deck_id": state["deck_id"],
            "decision": args.decision,
            "qa_report_sha256": canonical_sha256(qa_report),
            "deck_consistency_report_sha256": canonical_sha256(report),
            "policy_sha256": canonical_sha256(evaluation),
            "accepted_at_utc": _utc_now_iso(),
            "reason_code": "warning_acceptance_rejected" if args.decision == "reject" else "warning_accepted",
        }
        # normalized message hash (write the normalized bytes to compute it deterministically)
        normalized_bytes = normalized.encode("utf-8")
        import hashlib
        acceptance["user_message_sha256"] = hashlib.sha256(normalized_bytes).hexdigest()
        validate_schema("warning_acceptance", acceptance, SCHEMA_DIR)
        write_once_p5_artifact(args.output, acceptance)
        if args.decision == "accept":
            if evaluation.get("policy_status") != "awaiting_warning_acceptance":
                raise ContractError([error("$.evaluation.policy_status", "accept requires awaiting_warning_acceptance policy status", "policy_mismatch")])
            updated = transition(state, "delivery_approved", artifact_updates={"warning_acceptance_sha256": canonical_sha256(acceptance), "warning_acceptance_decision": "accept"})
        else:
            updated = transition(state, "p5_failed", artifact_updates={"warning_acceptance_sha256": canonical_sha256(acceptance), "warning_acceptance_decision": "reject"})
        _save_state(args.state, updated)
        return {"acceptance": str(args.output.resolve()), "decision": args.decision, "user_message_sha256": acceptance["user_message_sha256"]}
    if args.command == "create-decision":
        state = _load_state(args.state)
        qa_report = load_json(args.qa_report)
        roundtrip_report = load_json(args.roundtrip_report)
        deck_report = load_json(args.deck_consistency_report)
        evaluation = load_json(args.evaluation)
        p4_candidate_report = load_json(args.p4_candidate_report)
        candidate_sha = file_sha256(args.candidate_pptx)
        # Pre-flight verification
        failures: list[dict] = []
        if state["state"] != "delivery_approved":
            failures.append(error("$.state", "create-decision requires delivery_approved", "invalid_state"))
        if evaluation["policy_status"] not in {"pass", "awaiting_warning_acceptance"}:
            failures.append(error("$.evaluation.policy_status", "decision requires pass or awaiting_warning_acceptance policy", "policy_mismatch"))
        if evaluation["severity_counts"]["critical"] or evaluation["severity_counts"]["major"] or evaluation["review_incomplete"] or evaluation["unexpected_reviewer_calls"]:
            failures.append(error("$.evaluation", "critical/major/review_incomplete/unexpected calls forbid a decision", "policy_mismatch"))
        if p4_candidate_report.get("candidate_pptx_sha256") != candidate_sha:
            failures.append(error("$.p4_candidate_report.candidate_pptx_sha256", "candidate does not match the P4 candidate report", "candidate_hash_mismatch"))
        references = {
            "qa_report_sha256": canonical_sha256(qa_report),
            "roundtrip_report_sha256": canonical_sha256(roundtrip_report),
            "deck_consistency_report_sha256": canonical_sha256(deck_report),
            "exception_review_hashes": [canonical_sha256(load_json(path)) for path in args.exception_review_record or []],
        }
        if evaluation["policy_status"] == "awaiting_warning_acceptance":
            if args.warning_acceptance is None:
                failures.append(error("$.warning_acceptance", "minor warnings require a valid warning acceptance", "warning_acceptance_missing"))
            else:
                acceptance = load_json(args.warning_acceptance)
                validate_schema("warning_acceptance", acceptance, SCHEMA_DIR)
                if acceptance.get("decision") != "accept" or acceptance.get("policy_sha256") != canonical_sha256(evaluation):
                    failures.append(error("$.warning_acceptance", "warning acceptance must be accept and bind the current policy", "warning_acceptance_invalid"))
        if failures:
            raise ContractError(failures)
        status = "pass_with_warnings" if evaluation["policy_status"] == "awaiting_warning_acceptance" else "pass"
        decision_doc = {
            "schema_version": "1.0",
            "artifact_type": "deck_delivery_decision",
            "deck_id": state["deck_id"],
            "status": status,
            "policy_summary": {key: evaluation["severity_counts"].get(key, 0) for key in ("critical", "major", "minor", "suggestion")} | {"review_incomplete": evaluation["review_incomplete"], "unexpected_reviewer_calls": evaluation["unexpected_reviewer_calls"]},
            "delivered_pptx_sha256": candidate_sha,
            "references": references,
            "p4_candidate_report_sha256": canonical_sha256(p4_candidate_report),
            "warning_approval": None if args.warning_acceptance is None else {"warning_acceptance_sha256": canonical_sha256(load_json(args.warning_acceptance)), "decision": "accept"},
            "upstream_revision": evaluation.get("upstream_revision"),
        }
        validate_schema("deck_delivery_decision", decision_doc, SCHEMA_DIR)
        write_once_p5_artifact(args.output, decision_doc)
        updated = transition(state, "packaging", artifact_updates={"deck_delivery_decision_sha256": canonical_sha256(decision_doc)})
        _save_state(args.state, updated)
        return {"decision": str(args.output.resolve()), "status": decision_doc["status"], "delivered_pptx_sha256": candidate_sha}
    if args.command == "lock-packaging-runtime":
        state = _load_state(args.state)
        if state["state"] not in {"delivery_approved", "packaging", "live_review_pending"}:
            raise ContractError([error("$.state", "lock-packaging-runtime requires delivery_approved, packaging, or live_review_pending", "invalid_state")])
        document = lock_packaging_runtime()
        write_once_p5_artifact(args.output, document)
        updated = state
        if state["state"] == "delivery_approved":
            updated = transition(state, "packaging", artifact_updates={"delivery_packaging_runtime_lock_sha256": canonical_sha256(document)})
        else:
            updated = dict(state)
            updated["current_artifacts"] = dict(state["current_artifacts"])
            updated["current_artifacts"]["delivery_packaging_runtime_lock_sha256"] = canonical_sha256(document)
        _save_state(args.state, updated)
        return {"runtime_lock": str(args.output.resolve()), "lock_sha256": canonical_sha256(document)}
    if args.command == "package":
        state = _load_state(args.state)
        lock_document = load_json(args.runtime_lock)
        validate_schema("delivery_packaging_runtime_lock", lock_document, SCHEMA_DIR)
        previews = {
            "approved-preview-contact-sheet.png": args.contact_sheets_dir / "approved-preview-contact-sheet.png",
            "final-candidate-contact-sheet.png": args.contact_sheets_dir / "final-candidate-contact-sheet.png",
            "approved-vs-final-comparison-sheet.png": args.contact_sheets_dir / "approved-vs-final-comparison-sheet.png",
            "manifest.json": args.final_render_manifest,
        }
        for index, item in enumerate(sorted(args.final_renders_dir.glob("slide-*.png"))):
            previews[f"slides/final-slide-{index + 1:03d}.png"] = item
        p4_asset_manifest = load_json(args.p4_asset_manifest)
        from schema_utils import is_safe_relative_path as _safe_rel
        assets: list[tuple[str, Path]] = []
        for item in p4_asset_manifest.get("assets", []):
            relative = item.get("path", "")
            if not _safe_rel(relative):
                raise ContractError([error("$.assets", "asset manifest contains an unsafe path", "path_escape")])
            assets.append(("assets/" + relative, (args.p4_evidence_root / relative).resolve()))
        authority_hashes = {
            "p4_state_sha256": state["current_artifacts"].get("p4_state_sha256", ""),
            "p4_manifest_sha256": state["current_artifacts"].get("p4_manifest_sha256", ""),
            "p4_candidate_report_sha256": state["current_artifacts"].get("p4_candidate_report_sha256", ""),
            "p4_drift_report_sha256": state["current_artifacts"].get("p4_drift_report_sha256", ""),
            "p4_render_report_sha256": state["current_artifacts"].get("p4_render_report_sha256", ""),
            "p5_final_render_manifest_sha256": state["current_artifacts"].get("p5_final_render_manifest_sha256", ""),
            "powerpoint_roundtrip_report_sha256": state["current_artifacts"].get("powerpoint_roundtrip_report_sha256", ""),
            "deck_consistency_report_sha256": state["current_artifacts"].get("deck_consistency_report_sha256", ""),
            "deck_delivery_decision_sha256": state["current_artifacts"].get("deck_delivery_decision_sha256", ""),
        }
        if args.mode == "candidate":
            if args.work_root is None:
                raise ContractError([error("$.work_root", "candidate mode requires --work-root", "cli_error")])
            result = build_package_candidate(
                deck_id=state["deck_id"], output_name=args.output_name, candidate_pptx=args.candidate_pptx,
                work_root=args.work_root, lock_document=lock_document, previews=previews, assets=assets,
                asset_manifest=args.p4_asset_manifest, preview_manifest=args.final_render_manifest,
                qa_report=args.qa_report, roundtrip_report=args.roundtrip_report, authority_hashes=authority_hashes,
            )
            updated = dict(state)
            updated["current_artifacts"] = dict(state["current_artifacts"])
            updated["current_artifacts"]["package_candidate_dir"] = result["candidate_dir"]
            _save_state(args.state, updated)
            return {"candidate_dir": result["candidate_dir"], "delivery_forbidden": True, "formal_delivery_created": False, "package_candidate_hash_closure": "pass", "files": result["files"]}
        # formal mode
        if args.deck_consistency_report is None or args.decision is None or args.dist_root is None:
            raise ContractError([error("$.package", "formal mode requires --deck-consistency-report, --decision, and --dist-root", "cli_error")])
        result = package_formal_delivery(
            deck_id=state["deck_id"], output_name=args.output_name, candidate_pptx=args.candidate_pptx,
            dist_root=args.dist_root, lock_document=lock_document, previews=previews, assets=assets,
            asset_manifest=args.p4_asset_manifest, preview_manifest=args.final_render_manifest,
            qa_report=args.qa_report, deck_consistency_report=args.deck_consistency_report,
            roundtrip_report=args.roundtrip_report, decision=args.decision, state=state,
            p4_candidate_sha=state["current_artifacts"].get("candidate_deck_sha256", ""),
            authority_hashes=authority_hashes,
            reviewer_summary={
                "exception_reviewer_calls": state["counters"]["exception_reviewer_calls"],
                "deck_reviewer_calls": state["counters"]["deck_reviewer_calls"],
                "unexpected_reviewer_calls": state["counters"]["unexpected_reviewer_calls"],
                "review_mode": state["current_artifacts"].get("review_mode", "deterministic_fixture"),
            },
        )
        updated = transition(state, "delivered", artifact_updates={"provenance_sha256": result["provenance_sha256"], "delivery_files": result["files"]})
        _save_state(args.state, updated)
        return {"dist": result["dist"], "delivered_pptx_sha256": result["delivered_pptx_sha256"], "provenance_sha256": result["provenance_sha256"], "files": result["files"], "idempotent": result["idempotent"]}
    if args.command == "verify":
        state = _load_state(args.state)
        failures: list[dict] = []
        if state["state"] not in {"delivered", "live_review_pending"}:
            failures.append(error("$.state", "P5 delivery state is not at a valid verification point", "invalid_state"))
        if state["counters"]["unexpected_reviewer_calls"]:
            failures.append(error("$.counters.unexpected_reviewer_calls", "unexpected reviewer calls must be zero", "unexpected_reviewer_calls"))
        if failures:
            raise ContractError(failures)
        if state["state"] == "delivered" and args.delivery_dir is not None:
            if args.dist_root is None:
                raise ContractError([error("$.dist_root", "verify of a formal delivery requires --dist-root", "cli_error")])
            verification = verify_delivery(target=args.delivery_dir, provenance_expected_sha256=state["current_artifacts"].get("provenance_sha256", ""), dist_root=args.dist_root)
            return {"deck_id": state["deck_id"], "state": "delivered", "delivery_artifact_hash_closure": verification["delivery_artifact_hash_closure"], "files": verification["files"]}
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
