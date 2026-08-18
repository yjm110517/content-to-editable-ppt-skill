from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from reconstruction_authority import SCHEMA_DIR, file_sha256
from reconstruction_spec import validate_reconstruction_spec
from schema_utils import ContractError, error, load_json, validate_schema


SMOKE_CLASSES = {"native_text", "native_shape", "native_chart", "sanitized_svg", "reusable_raster", "generated_foreground"}
PATCH_PATH = re.compile(r"^/elements/(?P<index>[0-9]+)/(?:normalized_bbox/(?:x|y|w|h)|z_index|implementation/(?:margin_milli|alignment|vertical_alignment|line_spacing_milli|font_size_pt|fit|crop|style_seed/(?:fill_color|border_color|corner_radius|shadow_token|opacity_milli)|chart_spec/(?:show_legend|show_value|number_format|color_tokens)))$")


def select_smoke_set(specs: list[dict[str, Any]], high_risk_slide_ids: list[str] | None = None) -> dict[str, Any]:
    if not specs:
        raise ContractError([error("$.specs", "at least one page spec is required", "missing_authority")])
    high_risk = set(high_risk_slide_ids or [])
    deck_classes = {item["reconstruction_class"] for spec in specs for item in spec["elements"]} & SMOKE_CLASSES
    remaining = set(deck_classes); selected: list[dict[str, Any]] = []
    candidates = list(specs)
    while candidates and remaining and len(selected) < 2:
        ranked = sorted(candidates, key=lambda spec: (-len(({item["reconstruction_class"] for item in spec["elements"]} & remaining)), spec["slide_id"] not in high_risk, spec["order"], spec["slide_id"]))
        best = ranked[0]; gain = {item["reconstruction_class"] for item in best["elements"]} & remaining
        if not gain and selected:
            break
        selected.append(best); remaining -= gain; candidates.remove(best)
    if not selected:
        selected = [min(specs, key=lambda spec: spec["order"])]
    return {"schema_version":"1.0","artifact_type":"reconstruction_smoke_set","deck_id":specs[0]["deck_id"],"slide_ids":[item["slide_id"] for item in selected],"covered_classes":sorted(deck_classes-remaining),"uncovered_classes":sorted(remaining),"production_fixture_required":bool(remaining),"page_limit":2,"status":"selected"}


def _pointer_get(document: Any, pointer: str) -> Any:
    current = document
    for token in pointer.strip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def _pointer_set(document: Any, pointer: str, value: Any) -> None:
    tokens = pointer.strip("/").split("/"); current = document
    for token in tokens[:-1]: current = current[int(token)] if isinstance(current, list) else current[token]
    final = tokens[-1]
    if isinstance(current, list): current[int(final)] = value
    else: current[final] = value


def apply_targeted_patch(spec: dict[str, Any], seed_view: dict[str, Any], validation_report: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    validate_schema("visual_reconstruction_spec", spec, SCHEMA_DIR); validate_schema("reconstruction_seed_view", seed_view, SCHEMA_DIR); validate_schema("reconstruction_validation_report", validation_report, SCHEMA_DIR); validate_schema("reconstruction_patch", patch, SCHEMA_DIR)
    failures: list[dict[str, str]] = []
    if patch["base_spec_sha256"] != canonical_sha256(spec) or validation_report["spec_sha256"] != canonical_sha256(spec): failures.append(error("$.base_spec_sha256", "patch and report must bind current spec", "authority_hash_mismatch"))
    if patch["deck_id"] != spec["deck_id"] or patch["slide_id"] != spec["slide_id"]: failures.append(error("$.deck_id", "patch identity mismatch", "authority_deck_mismatch"))
    issue_by_id = {item["validation_issue_id"]: item for item in validation_report["issues"]}
    candidate = copy.deepcopy(spec)
    for index, operation in enumerate(patch["operations"]):
        base = f"$.operations[{index}]"; match = PATCH_PATH.fullmatch(operation["path"]); issue = issue_by_id.get(operation["validation_issue_id"])
        if match is None: failures.append(error(base + ".path", "field is outside targeted patch allowlist", "patch_field_forbidden")); continue
        if issue is None or issue["classification"] not in {"correctable", "reviewer_candidate"}: failures.append(error(base + ".validation_issue_id", "operation is not bound to a correctable issue", "patch_issue_mismatch")); continue
        if not (operation["path"].startswith(issue["path"].replace("$", "").replace("[", "/").replace("]", "").replace(".", "/")) or issue["path"].startswith(f"$.elements[{match.group('index')}]")):
            failures.append(error(base + ".validation_issue_id", "issue does not target this element", "patch_issue_mismatch")); continue
        try: current = _pointer_get(candidate, operation["path"])
        except (KeyError, IndexError, TypeError, ValueError): failures.append(error(base + ".path", "patch target does not exist", "patch_target_missing")); continue
        if current != operation["before"]: failures.append(error(base + ".before", "before value differs from current spec", "patch_before_mismatch")); continue
        if operation["path"].endswith("/font_size_pt"):
            element = candidate["elements"][int(match.group("index"))]; minimum = element["implementation"].get("minimum_font_size_pt", 1)
            if not isinstance(operation["after"], (int, float)) or operation["after"] < minimum: failures.append(error(base + ".after", "font size cannot be below frozen minimum", "patch_value_forbidden")); continue
        _pointer_set(candidate, operation["path"], copy.deepcopy(operation["after"]))
    if failures: raise ContractError(failures)
    report = validate_reconstruction_spec(candidate, seed_view, allow_targeted_changes=True)
    blocking = [item for item in report["issues"] if item["classification"] == "blocking"]
    if blocking: raise ContractError([error(item["path"], item["message"], item["code"]) for item in blocking])
    return candidate


def create_reconstruction_manifest(*, deck_id: str, approved_manifest_sha256: str, asset_manifest_sha256: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(pages, key=lambda item: item["order"])
    if [item["order"] for item in ordered] != list(range(1, len(ordered)+1)) or len({item["slide_id"] for item in ordered}) != len(ordered): raise ContractError([error("$.pages", "slide order and ids must be unique and contiguous", "manifest_order_mismatch")])
    manifest = {"schema_version":"1.0","artifact_type":"reconstruction_manifest","deck_id":deck_id,"approved_design_preview_manifest_sha256":approved_manifest_sha256,"asset_manifest_sha256":asset_manifest_sha256,"slides":ordered,"status":"pages_reconstructed"}
    validate_schema("reconstruction_manifest", manifest, SCHEMA_DIR); return manifest


def compare_assembly(*, manifest_path: Path, candidate_deck_path: Path, candidate_render_report_path: Path, reconstruction_root: Path, candidate_render_root: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path); render = load_json(candidate_render_report_path); validate_schema("reconstruction_manifest", manifest, SCHEMA_DIR)
    failures: list[dict[str, str]] = []; slides = []
    if render.get("ppt_sha256") != file_sha256(candidate_deck_path): failures.append(error("$.candidate_render.ppt_sha256", "candidate deck render binds another PPTX", "authority_hash_mismatch"))
    rendered = {item["order"]: item for item in render.get("slides", [])}
    for entry in manifest["slides"]:
        page_render = (reconstruction_root / Path(*entry["page_render_path"].split("/"))).resolve(); candidate = rendered.get(entry["order"])
        if not page_render.is_file() or candidate is None: failures.append(error("$.slides", f"render evidence missing for {entry['slide_id']}", "missing_authority")); continue
        assembled = (candidate_render_root / candidate["path"]).resolve(); page_hash = file_sha256(page_render); assembled_hash = file_sha256(assembled)
        if page_hash != entry["page_render_sha256"] or assembled_hash != candidate["sha256"]: failures.append(error("$.slides", f"render hash mismatch for {entry['slide_id']}", "authority_hash_mismatch"))
        identical = page_hash == assembled_hash; slides.append({"slide_id":entry["slide_id"],"order":entry["order"],"page_render_sha256":page_hash,"assembled_render_sha256":assembled_hash,"pixel_identical":identical,"drift_code":None if identical else "assembly_mutation"})
    drift = sum(not item["pixel_identical"] for item in slides); mutation = drift + len(failures)
    result = {"schema_version":"1.0","artifact_type":"post_assembly_drift_report","deck_id":manifest["deck_id"],"candidate_deck_sha256":file_sha256(candidate_deck_path),"slides":slides,"post_assembly_slide_drift":drift,"unexpected_assembly_mutation":mutation,"status":"pass" if mutation==0 and len(slides)==len(manifest["slides"]) else "fail"}
    validate_schema("post_assembly_drift_report", result, SCHEMA_DIR); return result
