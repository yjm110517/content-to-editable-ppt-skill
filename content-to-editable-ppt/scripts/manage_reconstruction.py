from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from canonical_artifact import canonical_sha256
from reconstruction_authority import (
    SCHEMA_DIR,
    atomic_write_json,
    build_reconstruction_asset_manifest,
    build_seed_view,
    load_reconstruction_authority,
)
from reconstruction_state import initial_deck_state, transition
from reconstruction_spec import compile_reconstruction_spec, validate_reconstruction_spec
from reconstruction_qa import compare_visual_fidelity, inspect_reconstruction_page
from reconstruction_workflow import apply_targeted_patch, compare_assembly, select_smoke_set
from schema_utils import ContractError, error, load_json, validate_schema


def _pairs(values: list[str] | None, option: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values or []:
        if "=" not in value:
            raise ContractError([error(option, "expected KEY=PATH", "cli_error")])
        key, raw = value.split("=", 1)
        if not key or key in result:
            raise ContractError([error(option, "key must be non-empty and unique", "cli_error")])
        result[key] = Path(raw)
    return result


def _base_authority(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--p3-state", type=Path, required=True)
    parser.add_argument("--approved-manifest", type=Path, required=True)
    parser.add_argument("--page-root", action="append", required=True, help="SLIDE_ID=directory")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage deterministic P4 constrained reconstruction.")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init")
    _base_authority(init)
    init.add_argument("--state", type=Path, required=True)

    assets = commands.add_parser("build-asset-manifest")
    assets.add_argument("--deck-id", required=True)
    assets.add_argument("--evidence-root", type=Path, required=True)
    assets.add_argument("--approved-record", type=Path, action="append", required=True)
    assets.add_argument("--output", type=Path, required=True)

    seed = commands.add_parser("build-seed-view")
    _base_authority(seed)
    seed.add_argument("--slide-id", required=True)
    seed.add_argument("--approved-content", type=Path, required=True)
    seed.add_argument("--visual-system", type=Path, required=True)
    seed.add_argument("--text-footprints", type=Path, required=True)
    seed.add_argument("--asset-manifest", type=Path, required=True)
    seed.add_argument("--chart-spec", action="append", help="VISUAL_REF=chart-spec.json")
    seed.add_argument("--output", type=Path, required=True)

    compile_spec = commands.add_parser("compile-spec")
    compile_spec.add_argument("--seed-view", type=Path, required=True)
    compile_spec.add_argument("--order", type=int, required=True)
    compile_spec.add_argument("--order-sensitive", action="store_true")
    compile_spec.add_argument("--order-binding", action="append", help="NAME=VALUE")
    compile_spec.add_argument("--output", type=Path, required=True)

    validate_spec = commands.add_parser("validate-spec")
    validate_spec.add_argument("--spec", type=Path, required=True)
    validate_spec.add_argument("--seed-view", type=Path, required=True)
    validate_spec.add_argument("--report", type=Path, required=True)

    build_page = commands.add_parser("build-page")
    build_page.add_argument("--spec", type=Path, required=True); build_page.add_argument("--asset-manifest", type=Path, required=True); build_page.add_argument("--evidence-root", type=Path, required=True)
    build_page.add_argument("--output", type=Path, required=True); build_page.add_argument("--report", type=Path, required=True); build_page.add_argument("--node", default=os.environ.get("IVT_NODE", "node"))

    render_page = commands.add_parser("render-page")
    render_page.add_argument("--input", type=Path, required=True); render_page.add_argument("--output-dir", type=Path, required=True); render_page.add_argument("--report", type=Path, required=True); render_page.add_argument("--width-px", type=int, required=True); render_page.add_argument("--height-px", type=int, required=True)

    verify_page = commands.add_parser("verify-page")
    verify_page.add_argument("--spec", type=Path, required=True); verify_page.add_argument("--pptx", type=Path, required=True); verify_page.add_argument("--build-report", type=Path, required=True); verify_page.add_argument("--output", type=Path, required=True)

    compare = commands.add_parser("compare-preview")
    compare.add_argument("--deck-id", required=True); compare.add_argument("--slide-id", required=True); compare.add_argument("--approved-preview", type=Path, required=True); compare.add_argument("--candidate-render", type=Path, required=True); compare.add_argument("--output", type=Path, required=True)

    smoke = commands.add_parser("select-smoke-set")
    smoke.add_argument("--spec", type=Path, action="append", required=True); smoke.add_argument("--high-risk-slide-id", action="append"); smoke.add_argument("--output", type=Path, required=True)

    patch = commands.add_parser("apply-targeted-patch")
    patch.add_argument("--spec", type=Path, required=True); patch.add_argument("--seed-view", type=Path, required=True); patch.add_argument("--validation-report", type=Path, required=True); patch.add_argument("--patch", type=Path, required=True); patch.add_argument("--output", type=Path, required=True)

    assemble = commands.add_parser("assemble-candidate-deck")
    assemble.add_argument("--manifest", type=Path, required=True); assemble.add_argument("--reconstruction-root", type=Path, required=True); assemble.add_argument("--asset-manifest", type=Path, required=True); assemble.add_argument("--evidence-root", type=Path, required=True); assemble.add_argument("--output", type=Path, required=True); assemble.add_argument("--report", type=Path, required=True); assemble.add_argument("--node", default=os.environ.get("IVT_NODE", "node"))

    assembly = commands.add_parser("compare-assembly")
    assembly.add_argument("--manifest", type=Path, required=True); assembly.add_argument("--candidate-deck", type=Path, required=True); assembly.add_argument("--candidate-render-report", type=Path, required=True); assembly.add_argument("--reconstruction-root", type=Path, required=True); assembly.add_argument("--candidate-render-root", type=Path, required=True); assembly.add_argument("--output", type=Path, required=True)

    verify = commands.add_parser("verify-authority")
    _base_authority(verify)
    return parser


def _load_bundle(args: argparse.Namespace) -> dict:
    return load_reconstruction_authority(p3_state_path=args.p3_state, approved_manifest_path=args.approved_manifest, page_roots=_pairs(args.page_root, "--page-root"))


def run(args: argparse.Namespace) -> dict:
    if args.command == "init":
        bundle = _load_bundle(args)
        state = initial_deck_state(bundle["deck_id"], bundle["manifest_sha256"])
        state = transition(state, "reconstruction_preflight")
        validate_schema("reconstruction_deck_state", state, SCHEMA_DIR)
        atomic_write_json(args.state, state)
        return {"state": str(args.state.resolve()), "deck_id": bundle["deck_id"], "state_name": state["state"]}
    if args.command == "build-asset-manifest":
        manifest = build_reconstruction_asset_manifest(deck_id=args.deck_id, evidence_root=args.evidence_root, record_paths=args.approved_record)
        atomic_write_json(args.output, manifest)
        return {"asset_manifest": str(args.output.resolve()), "asset_manifest_sha256": canonical_sha256(manifest), "asset_count": len(manifest["assets"])}
    if args.command == "build-seed-view":
        bundle = _load_bundle(args)
        page = next((item for item in bundle["pages"] if item["slide_id"] == args.slide_id), None)
        if page is None:
            raise ContractError([error("$.slide_id", "slide is not in current approved manifest", "unknown_slide")])
        charts = {key: load_json(path) for key, path in _pairs(args.chart_spec, "--chart-spec").items()}
        view = build_seed_view(page=page, approved_content=load_json(args.approved_content), visual_system=load_json(args.visual_system), text_footprints=load_json(args.text_footprints), asset_manifest=load_json(args.asset_manifest), chart_specs=charts)
        atomic_write_json(args.output, view)
        return {"seed_view": str(args.output.resolve()), "seed_view_sha256": canonical_sha256(view), "seed_count": len(view["seeds"])}
    if args.command == "compile-spec":
        raw_context = _pairs(args.order_binding, "--order-binding")
        context: dict[str, object] = {}
        for key, value in raw_context.items():
            text = str(value)
            context[key] = int(text) if key in {"slide_ordinal", "section_ordinal", "total_slide_count"} else None if text == "null" else text
        spec = compile_reconstruction_spec(load_json(args.seed_view), order=args.order, order_sensitive=args.order_sensitive, order_bindings=list(context), order_context=context)
        atomic_write_json(args.output, spec)
        return {"spec": str(args.output.resolve()), "spec_sha256": canonical_sha256(spec), "page_input_sha256": spec["page_input_sha256"]}
    if args.command == "validate-spec":
        report = validate_reconstruction_spec(load_json(args.spec), load_json(args.seed_view))
        atomic_write_json(args.report, report)
        return {"report": str(args.report.resolve()), "status": report["status"], "issue_count": len(report["issues"])}
    if args.command == "build-page":
        command = [args.node, str(Path(__file__).with_name("build_reconstruction_page.mjs")), "--spec", str(args.spec), "--asset-manifest", str(args.asset_manifest), "--evidence-root", str(args.evidence_root), "--output", str(args.output), "--report", str(args.report), "--python", sys.executable]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if completed.returncode:
            raise ContractError([error("$.build_page", completed.stdout.strip() or completed.stderr.strip(), "page_build_failed")])
        return {"pptx": str(args.output.resolve()), "report": str(args.report.resolve())}
    if args.command == "render-page":
        command = [sys.executable, str(Path(__file__).with_name("render_reconstruction_deck.py")), "--input", str(args.input), "--output-dir", str(args.output_dir), "--report", str(args.report), "--width-px", str(args.width_px), "--height-px", str(args.height_px)]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if completed.returncode:
            raise ContractError([error("$.render_page", completed.stdout.strip() or completed.stderr.strip(), "powerpoint_render_failed")])
        return {"render_dir": str(args.output_dir.resolve()), "report": str(args.report.resolve())}
    if args.command == "verify-page":
        report = inspect_reconstruction_page(pptx_path=args.pptx, spec_path=args.spec, build_report_path=args.build_report)
        atomic_write_json(args.output, report)
        if report["status"] != "pass": raise ContractError(report["blocking_issues"])
        return {"qa_report": str(args.output.resolve()), "status": "pass"}
    if args.command == "compare-preview":
        report = compare_visual_fidelity(deck_id=args.deck_id, slide_id=args.slide_id, approved_preview=args.approved_preview, candidate_render=args.candidate_render)
        atomic_write_json(args.output, report)
        return {"fidelity_report": str(args.output.resolve()), "classification": report["classification"]}
    if args.command == "select-smoke-set":
        result = select_smoke_set([load_json(path) for path in args.spec], args.high_risk_slide_id)
        atomic_write_json(args.output, result)
        return {"smoke_set": str(args.output.resolve()), "slide_ids": result["slide_ids"], "uncovered_classes": result["uncovered_classes"]}
    if args.command == "apply-targeted-patch":
        result = apply_targeted_patch(load_json(args.spec), load_json(args.seed_view), load_json(args.validation_report), load_json(args.patch))
        atomic_write_json(args.output, result)
        return {"spec": str(args.output.resolve()), "spec_sha256": canonical_sha256(result)}
    if args.command == "assemble-candidate-deck":
        command = [args.node, str(Path(__file__).with_name("build_reconstruction_deck.mjs")), "--manifest", str(args.manifest), "--reconstruction-root", str(args.reconstruction_root), "--asset-manifest", str(args.asset_manifest), "--evidence-root", str(args.evidence_root), "--output", str(args.output), "--report", str(args.report), "--python", sys.executable]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if completed.returncode: raise ContractError([error("$.assemble_candidate_deck", completed.stdout.strip() or completed.stderr.strip(), "candidate_deck_build_failed")])
        return {"candidate_deck": str(args.output.resolve()), "report": str(args.report.resolve())}
    if args.command == "compare-assembly":
        result = compare_assembly(manifest_path=args.manifest, candidate_deck_path=args.candidate_deck, candidate_render_report_path=args.candidate_render_report, reconstruction_root=args.reconstruction_root, candidate_render_root=args.candidate_render_root)
        atomic_write_json(args.output, result)
        return {"report": str(args.output.resolve()), "status": result["status"], "post_assembly_slide_drift": result["post_assembly_slide_drift"]}
    if args.command == "verify-authority":
        bundle = _load_bundle(args)
        return {"deck_id": bundle["deck_id"], "approved_manifest_sha256": bundle["manifest_sha256"], "slide_ids": [item["slide_id"] for item in bundle["pages"]]}
    raise AssertionError(args.command)


def main() -> int:
    try:
        args = build_parser().parse_args()
        outputs = run(args)
        print(json.dumps({"status": "ok", "outputs": outputs, "error": None}, ensure_ascii=False))
        return 0
    except Exception as exc:
        issues = exc.errors if isinstance(exc, ContractError) else [{"path": "$", "code": "p4_internal_error", "message": str(exc)}]
        print(json.dumps({"status": "error", "outputs": {}, "error": {"issues": issues}}, ensure_ascii=False))
        return 4 if isinstance(exc, ContractError) else 70


if __name__ == "__main__":
    raise SystemExit(main())
