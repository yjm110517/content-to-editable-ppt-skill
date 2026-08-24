from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from deck_preview_workflow import approve as approve_deck, contact_sheet
from design_preview_batch import initial_state, refresh_state, sha256_file, update_page, validate_map_evidence
from design_preview_contract import validate_element_map
from finalize_preview_build import main as _unused  # noqa: F401
from preview_projector import project_preview
from schema_utils import ContractError, error, load_json, validate_schema
from style_anchor_workflow import record_preview


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
SCRIPTS = Path(__file__).resolve().parent


def _bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _write_once(path: Path, value: dict[str, Any]) -> None:
    data = _bytes(value)
    if path.exists():
        if path.read_bytes() == data:
            return
        raise ContractError([error(str(path), "immutable artifact already exists with different bytes", "overwrite_forbidden")])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _replace_state(path: Path, state: dict[str, Any]) -> None:
    validate_schema("design_preview_batch_state", state, SCHEMA_DIR)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_bytes(state))
    os.replace(temporary, path)


def _state(path: Path) -> dict[str, Any]:
    value = load_json(path)
    validate_schema("design_preview_batch_state", value, SCHEMA_DIR)
    return value


def _safe_copy(source: Path, target: Path) -> None:
    if target.exists():
        if sha256_file(source) == sha256_file(target):
            return
        raise ContractError([error(str(target), "artifact already exists with different bytes", "overwrite_forbidden")])
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _page_record(state: dict[str, Any], slide_id: str) -> dict[str, Any]:
    matches = [item for item in state["pages"] if item["slide_id"] == slide_id]
    if len(matches) != 1:
        raise ContractError([error("$.slide_id", "unknown or duplicate slide id", "unknown_slide")])
    return matches[0]


def _slide_content(slide_content_dir: Path, slide_id: str) -> dict[str, Any]:
    manifest = load_json(slide_content_dir / "projection-manifest.json")
    matches = [item for item in manifest["slides"] if item["slide_id"] == slide_id]
    if len(matches) != 1:
        raise ContractError([error("$.slide_content", "projection manifest does not contain slide exactly once", "slide_set_mismatch")])
    return load_json(slide_content_dir / matches[0]["path"])


def _run(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise ContractError([error("$.runtime", result.stderr.strip() or result.stdout.strip() or "preview runtime failed", "runtime_failure")])


def _authority(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    package = load_json(args.prompt_package)
    system = load_json(args.visual_system)
    footprints = load_json(args.footprints)
    lock = load_json(args.runtime_lock)
    for kind, value in (("deck_prompt_package", package), ("deck_visual_system", system), ("text_footprint_manifest", footprints), ("generation_runtime_lock", lock)):
        validate_schema(kind, value, SCHEMA_DIR)
    if not (package["deck_id"] == system["deck_id"] == footprints["deck_id"] == lock["deck_id"]):
        raise ContractError([error("$.deck_id", "P3.2 authority artifacts are cross-deck", "deck_mismatch")])
    return package, system, footprints, lock


def _map_input_manifest(*, deck_id: str, slide_id: str, package: dict[str, Any], prompt_package_path: Path, raw: Path, content: dict[str, Any], system_path: Path, output: Path) -> dict[str, Any]:
    slide = next(item for item in package["slides"] if item["slide_id"] == slide_id)
    schema = SCHEMA_DIR / "design-element-map.schema.json"
    input_dir = output / "inputs"
    values: list[tuple[str, str, Path, str]] = [
        ("generated-layer.png", "generated-layer.png", raw, "generated_visual_layer"),
        ("deck-prompt-package.json", "deck-prompt-package.json", prompt_package_path, "prompt_package"),
        ("element-intents.json", "element-intents.json", output / ".element-intents.json", "element_intents"),
        ("slide-content.json", "slide-content.json", output / ".slide-content.json", "approved_slide_content"),
        ("deck-visual-system.json", "deck-visual-system.json", system_path, "deck_visual_system"),
        ("design-element-map.schema.json", "design-element-map.schema.json", schema, "response_schema"),
    ]
    _write_once(output / ".element-intents.json", {"slide_id": slide_id, "element_intents": slide["element_intents"], "visual_placeholders": [item for item in slide["element_intents"] if item["source_ref"].endswith("V01")]})
    _write_once(output / ".slide-content.json", content)
    for _name, filename, source, _purpose in values:
        _safe_copy(source, input_dir / filename)
    entries = []
    for name, filename, _source, purpose in values:
        target = input_dir / filename
        entries.append({"name": name, "filename": filename, "sha256": sha256_file(target), "media_type": "image/png" if filename.endswith(".png") else ("application/schema+json" if filename.endswith(".schema.json") else "application/json"), "purpose": purpose})
    manifest = {"schema_version": "1.0", "artifact_type": "design_element_map_input_manifest", "deck_id": deck_id, "slide_id": slide_id, "prompt_package_sha256": canonical_sha256(package), "generated_layer_sha256": sha256_file(raw), "inputs": entries}
    validate_schema("design_element_map_input_manifest", manifest, SCHEMA_DIR)
    _write_once(output / "map-input-manifest.json", manifest)
    prompt = """# P3.3 Element Map Host Pass

Return one JSON object conforming exactly to `design-element-map.schema.json`.
Describe only visual elements actually present in the Generated Layer. Do not redesign, move, add, remove, or rewrite content. Map every provided Element Intent exactly once. Classify every Critical or Major generated visual with a Reconstruction Class and P4 Strategy. Formal text is compositor-owned `native_text`; do not claim it is in the image. Reject generated text, logos, labels, duplicate resolved icons, chart data, or an unclassified major visual by setting the corresponding audit field. A native shape requires shape kind, BBox, fill, border, radius, opacity, shadow class and relationship references.
"""
    target = output / "map-prompt.md"
    if target.exists() and target.read_text(encoding="utf-8") != prompt:
        raise ContractError([error(str(target), "map prompt changed after package creation", "overwrite_forbidden")])
    if not target.exists():
        target.write_text(prompt, encoding="utf-8", newline="\n")
    return manifest


def init(args: argparse.Namespace) -> dict[str, Any]:
    package, _system, _footprints, _lock = _authority(args)
    anchor = load_json(args.style_anchor_record); reference = load_json(args.style_reference_record); anchor_map = load_json(args.anchor_element_map); anchor_compat = load_json(args.anchor_compatibility); anchor_preview = load_json(args.anchor_final_preview)
    for kind, value in (("style_anchor_record", anchor), ("style_anchor_reference_record", reference), ("design_element_map", anchor_map), ("reconstruction_compatibility_report", anchor_compat), ("final_design_preview_record", anchor_preview)):
        validate_schema(kind, value, SCHEMA_DIR)
    if anchor["deck_id"] != package["deck_id"] or anchor["slide_id"] != package["style_anchor_slide_id"] or anchor_preview["final_preview_sha256"] != anchor["final_preview_sha256"]:
        raise ContractError([error("$.anchor", "approved Style Anchor does not bind current prompt package", "authority_hash_mismatch")])
    slides = [{"slide_id": item["slide_id"], "order": item["order"]} for item in package["slides"]]
    artifacts = {"deck_prompt_package_sha256": canonical_sha256(package), "deck_visual_system_sha256": canonical_sha256(_system), "text_footprint_manifest_sha256": canonical_sha256(_footprints), "generation_runtime_lock_sha256": canonical_sha256(_lock), "style_anchor_record_sha256": canonical_sha256(anchor), "style_anchor_reference_record_sha256": canonical_sha256(reference), "style_anchor_reference_sha256": reference["reference_sha256"], "approved_anchor_preview_sha256": anchor_preview["final_preview_sha256"]}
    state = initial_state(deck_id=package["deck_id"], slides=slides, artifacts=artifacts, anchor_slide_id=anchor["slide_id"])
    state = update_page(state, anchor["slide_id"], status="anchor_approved", element_map_sha256=canonical_sha256(anchor_map), compatibility_report_sha256=canonical_sha256(anchor_compat), final_preview_record_sha256=canonical_sha256(anchor_preview))
    state["counters"]["image_generation_calls"] = 1
    state["counters"]["host_map_pass_count"] = 1
    state["counters"]["map_correction_count"] = args.anchor_map_correction_count
    _write_once(args.state, state)
    return state


def register_layers(args: argparse.Namespace) -> dict[str, Any]:
    state = _state(args.state); package = load_json(args.prompt_package); validate_schema("deck_prompt_package", package, SCHEMA_DIR)
    for item in state["pages"]:
        if item["status"] == "anchor_approved":
            continue
        page_root = args.layers_root / item["slide_id"]
        record_path = page_root / "generated-visual-layer-record.json"
        record = load_json(record_path); validate_schema("generated_visual_layer_record", record, SCHEMA_DIR)
        generation = load_json(page_root / "generation-package" / "call_manifest.json")
        raw = page_root / record["image_path"]
        required = {"deck_id": state["deck_id"], "slide_id": item["slide_id"], "revision": 1, "generation_kind": "initial", "technical_retry_count": 0, "runtime_lock_sha256": state["current_artifacts"]["generation_runtime_lock_sha256"]}
        if any(generation.get(key) != value or record.get(key) != value for key, value in required.items()) or record["prompt_sha256"] != generation.get("prompt_sha256") or generation.get("style_anchor_reference_sha256") != state["current_artifacts"]["style_anchor_reference_sha256"] or not raw.is_file() or sha256_file(raw) != record["image_sha256"]:
            raise ContractError([error("$.generated_layer", f"Generated Layer does not bind {item['slide_id']}", "authority_hash_mismatch")])
        state = update_page(state, item["slide_id"], status="generated", generated_layer_record_sha256=canonical_sha256(record))
    state["counters"]["image_generation_calls"] = len(state["pages"])
    state = refresh_state(state); _replace_state(args.state, state); return state


def prepare_map_packages(args: argparse.Namespace) -> dict[str, Any]:
    state = _state(args.state); package = load_json(args.prompt_package); validate_schema("deck_prompt_package", package, SCHEMA_DIR)
    for item in state["pages"]:
        if item["status"] != "generated":
            continue
        sid = item["slide_id"]; record = load_json(args.layers_root / sid / "generated-visual-layer-record.json"); raw = args.layers_root / sid / record["image_path"]
        call_dir = args.map_root / sid
        if not call_dir.exists():
            content = _slide_content(args.slide_content_dir, sid)
            manifest = _map_input_manifest(deck_id=state["deck_id"], slide_id=sid, package=package, prompt_package_path=args.prompt_package, raw=raw, content=content, system_path=args.visual_system, output=call_dir)
            item_hash = canonical_sha256(manifest)
        else:
            manifest = load_json(call_dir / "map-input-manifest.json"); item_hash = canonical_sha256(manifest)
        state = update_page(state, sid, status="map_package_ready", map_input_manifest_sha256=item_hash)
    state = refresh_state(state); _replace_state(args.state, state); return state


def consume_map_evidence(args: argparse.Namespace) -> dict[str, Any]:
    state = _state(args.state); package = load_json(args.prompt_package); validate_schema("deck_prompt_package", package, SCHEMA_DIR)
    for item in state["pages"]:
        if item["status"] != "map_package_ready":
            continue
        sid = item["slide_id"]; record = load_json(args.layers_root / sid / "generated-visual-layer-record.json")
        evidence = validate_map_evidence(args.evidence_root / sid, deck_id=state["deck_id"], slide_id=sid, generated_layer_sha256=record["image_sha256"], prompt_package_sha256=canonical_sha256(package))
        if evidence["manifest_sha256"] != item["map_input_manifest_sha256"]:
            raise ContractError([error("$.map_input_manifest", "Map evidence does not bind prepared call package", "authority_hash_mismatch")])
        report = validate_element_map(evidence["element_map"], package)
        page_dir = args.pages_root / sid
        _write_once(page_dir / "element-map.json", evidence["element_map"])
        _write_once(page_dir / "reconstruction-compatibility-report.json", report)
        if report["status"] != "pass":
            state = update_page(state, sid, status="failed", map_call_record_sha256=canonical_sha256(evidence["record"]), element_map_sha256=canonical_sha256(evidence["element_map"]), compatibility_report_sha256=canonical_sha256(report), error_code="reconstruction_incompatible")
        else:
            state = update_page(state, sid, status="compatible", map_call_record_sha256=canonical_sha256(evidence["record"]), element_map_sha256=canonical_sha256(evidence["element_map"]), compatibility_report_sha256=canonical_sha256(report))
            state["counters"]["host_map_pass_count"] += 1
            state["counters"]["map_correction_count"] += evidence["record"]["map_correction_count"]
    state = refresh_state(state); _replace_state(args.state, state); return state


def build_previews(args: argparse.Namespace) -> dict[str, Any]:
    state = _state(args.state); package, system, footprints, _lock = _authority(args)
    for item in state["pages"]:
        if item["status"] != "compatible":
            continue
        sid = item["slide_id"]; page_dir = args.pages_root / sid; mapping = load_json(page_dir / "element-map.json"); compatibility = load_json(page_dir / "reconstruction-compatibility-report.json")
        record = load_json(args.layers_root / sid / "generated-visual-layer-record.json"); raw = args.layers_root / sid / record["image_path"]
        content = _slide_content(args.slide_content_dir, sid)
        preview_dir = page_dir / "preview"
        docs = project_preview(deck_id=state["deck_id"], slide_id=sid, content=content, element_map=mapping, visual_system=system, footprints=footprints, raw_layer=raw, output_dir=preview_dir)
        pptx = preview_dir / "preview.pptx"; summary = preview_dir / "build-summary.json"
        _run([str(args.node_path), str(SCRIPTS / "build_slide.mjs"), "--iteration-dir", str(preview_dir), "--layout", str(docs["layout"]), "--asset-manifest", str(docs["asset_manifest"]), "--asset-dir", str(docs["asset_dir"]), "--output", str(pptx), "--build-summary", str(summary), "--python", str(args.python_path), "--run-id", f"{state['deck_id']}-{sid}-preview", "--iteration", "1"])
        build_report = page_dir / "preview-powerpoint-build-report.json"
        _run([str(args.python_path), str(SCRIPTS / "finalize_preview_build.py"), "--deck-id", state["deck_id"], "--slide-id", sid, "--element-map", str(page_dir / "element-map.json"), "--compatibility-report", str(page_dir / "reconstruction-compatibility-report.json"), "--layout", str(docs["layout"]), "--asset-manifest", str(docs["asset_manifest"]), "--preview-pptx", str(pptx), "--output", str(build_report)])
        final = page_dir / "final-design-preview.png"; render_report = page_dir / "render-report.json"
        _run([str(args.python_path), str(SCRIPTS / "render_ppt.py"), "--input", str(pptx), "--layout", str(docs["layout"]), "--output", str(final), "--report", str(render_report), "--renderer", "powerpoint", "--run-id", f"{state['deck_id']}-{sid}-preview", "--iteration", "1"])
        output = page_dir / "final-design-preview-record.json"
        record_preview(Namespace(generated_layer_record=args.layers_root / sid / "generated-visual-layer-record.json", element_map=page_dir / "element-map.json", compatibility_report=page_dir / "reconstruction-compatibility-report.json", preview_build_report=build_report, powerpoint_render=final, output=output))
        state = update_page(state, sid, status="rendered", final_preview_record_sha256=canonical_sha256(load_json(output)))
    state = refresh_state(state); _replace_state(args.state, state); return state


def build_contact(args: argparse.Namespace) -> dict[str, Any]:
    state = _state(args.state)
    if state["state"] != "contact_sheet_ready":
        raise ContractError([error("$.state", "Contact Sheet requires every page to be rendered", "invalid_state")])
    records = [args.anchor_final_preview]
    images = [args.anchor_preview_image]
    for item in sorted(state["pages"], key=lambda value: value["order"]):
        if item["status"] == "anchor_approved":
            continue
        records.append(args.pages_root / item["slide_id"] / "final-design-preview-record.json")
        images.append(args.pages_root / item["slide_id"] / "final-design-preview.png")
    output_manifest = args.output_root / "approved-design-preview-manifest.json"; output_image = args.output_root / "contact-sheet.png"; output_record = args.output_root / "contact-sheet-record.json"
    contact_sheet(Namespace(style_anchor_record=args.style_anchor_record, preview_record=records, preview_image=images, output_manifest=output_manifest, output_image=output_image, output_record=output_record))
    state["current_artifacts"]["preview_manifest_sha256"] = canonical_sha256(load_json(output_manifest))
    state["current_artifacts"]["contact_sheet_record_sha256"] = canonical_sha256(load_json(output_record))
    state["state"] = "awaiting_deck_confirmation"; state["history"].append({"event": "contact_sheet_presented", "evidence": state["current_artifacts"]["contact_sheet_record_sha256"]})
    _replace_state(args.state, state); return state


def record_feedback(args: argparse.Namespace) -> dict[str, Any]:
    state = _state(args.state)
    if state["state"] != "awaiting_deck_confirmation":
        raise ContractError([error("$.state", "Deck feedback requires an awaiting Contact Sheet", "invalid_state")])
    approve_deck(Namespace(preview_manifest=args.preview_manifest, feedback=args.feedback, output=args.output_manifest))
    state["current_artifacts"]["approved_design_preview_manifest_sha256"] = canonical_sha256(load_json(args.output_manifest))
    state["state"] = "p3_3_complete"; state["history"].append({"event": "deck_previews_approved", "evidence": state["current_artifacts"]["approved_design_preview_manifest_sha256"]})
    _replace_state(args.state, state); return state


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Batch P3.3 Design Preview orchestration; it never calls a model internally.")
    commands = result.add_subparsers(dest="action", required=True)
    def authority(p: argparse.ArgumentParser) -> None:
        p.add_argument("--prompt-package", type=Path, required=True); p.add_argument("--visual-system", type=Path, required=True); p.add_argument("--footprints", type=Path, required=True); p.add_argument("--runtime-lock", type=Path, required=True)
    init_p = commands.add_parser("init"); authority(init_p); init_p.add_argument("--state", type=Path, required=True); init_p.add_argument("--style-anchor-record", type=Path, required=True); init_p.add_argument("--style-reference-record", type=Path, required=True); init_p.add_argument("--anchor-element-map", type=Path, required=True); init_p.add_argument("--anchor-compatibility", type=Path, required=True); init_p.add_argument("--anchor-final-preview", type=Path, required=True); init_p.add_argument("--anchor-map-correction-count", type=int, default=0)
    for name in ("register-layers", "prepare-map-packages", "consume-map-evidence"):
        p = commands.add_parser(name); p.add_argument("--state", type=Path, required=True); p.add_argument("--prompt-package", type=Path, required=True); p.add_argument("--layers-root", type=Path, required=True)
        if name == "prepare-map-packages": p.add_argument("--slide-content-dir", type=Path, required=True); p.add_argument("--visual-system", type=Path, required=True); p.add_argument("--map-root", type=Path, required=True)
        if name == "consume-map-evidence": p.add_argument("--evidence-root", type=Path, required=True); p.add_argument("--pages-root", type=Path, required=True)
    build = commands.add_parser("build-previews"); authority(build); build.add_argument("--state", type=Path, required=True); build.add_argument("--layers-root", type=Path, required=True); build.add_argument("--slide-content-dir", type=Path, required=True); build.add_argument("--pages-root", type=Path, required=True); build.add_argument("--python-path", type=Path, required=True); build.add_argument("--node-path", type=Path, required=True)
    contact = commands.add_parser("build-contact-sheet"); contact.add_argument("--state", type=Path, required=True); contact.add_argument("--pages-root", type=Path, required=True); contact.add_argument("--style-anchor-record", type=Path, required=True); contact.add_argument("--anchor-final-preview", type=Path, required=True); contact.add_argument("--anchor-preview-image", type=Path, required=True); contact.add_argument("--output-root", type=Path, required=True)
    feedback = commands.add_parser("record-feedback"); feedback.add_argument("--state", type=Path, required=True); feedback.add_argument("--preview-manifest", type=Path, required=True); feedback.add_argument("--feedback", type=Path, required=True); feedback.add_argument("--output-manifest", type=Path, required=True)
    resume = commands.add_parser("resume"); resume.add_argument("--state", type=Path, required=True); resume.add_argument("--prompt-package", type=Path, required=True); resume.add_argument("--layers-root", type=Path, required=True); resume.add_argument("--slide-content-dir", type=Path, required=True); resume.add_argument("--visual-system", type=Path, required=True); resume.add_argument("--map-root", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        actions = {"init": init, "register-layers": register_layers, "prepare-map-packages": prepare_map_packages, "consume-map-evidence": consume_map_evidence, "build-previews": build_previews, "build-contact-sheet": build_contact, "record-feedback": record_feedback}
        if args.action == "resume":
            register_layers(Namespace(state=args.state, prompt_package=args.prompt_package, layers_root=args.layers_root))
            state = prepare_map_packages(Namespace(state=args.state, prompt_package=args.prompt_package, layers_root=args.layers_root, slide_content_dir=args.slide_content_dir, visual_system=args.visual_system, map_root=args.map_root))
        else:
            state = actions[args.action](args)
        print(json.dumps({"status": "ok", "state": state["state"], "pages": [{"slide_id": item["slide_id"], "status": item["status"]} for item in state["pages"]]}, ensure_ascii=False)); return 0
    except (ContractError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        errors = exc.errors if isinstance(exc, ContractError) else [{"path": "$", "code": "design_preview_batch_error", "message": str(exc)}]
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False)); return 4


if __name__ == "__main__":
    raise SystemExit(main())
