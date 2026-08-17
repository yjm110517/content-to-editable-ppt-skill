from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from audit_fonts import _normalize_font, installed_font_names
from canonical_artifact import canonical_sha256
from markdown_wireframe import load_markdown_authority, sha256_bytes
from schema_utils import ContractError, error, is_safe_relative_path, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
FORBIDDEN_GUIDANCE = re.compile(r"(?i)(?:https?|file|data):|[A-Za-z]:\\|(?:^|[\\/])\.\.(?:[\\/]|$)|\.svg\b|\b[a-f0-9]{64}\b")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe(index_path: Path, relative: str) -> Path:
    if not is_safe_relative_path(relative):
        raise ContractError([error("$.icon_asset_index", "unsafe artifact path", "unsafe_path")])
    target = (index_path.parent / relative).resolve()
    try:
        target.relative_to(index_path.parent.resolve())
    except ValueError as exc:
        raise ContractError([error("$.icon_asset_index", "artifact path escapes index root", "unsafe_path")]) from exc
    return target


def validate_icon_asset_index(index_path: Path, p2_manifest: dict[str, Any]) -> dict[str, Any]:
    index = load_json(index_path)
    validate_schema("p3_icon_asset_authority_index", index, SCHEMA_DIR)
    p2_sha = canonical_sha256(p2_manifest)
    failures: list[dict[str, str]] = []
    if index["deck_id"] != p2_manifest["deck_id"] or index["p2_manifest_sha256"] != p2_sha:
        failures.append(error("$.icon_asset_index", "Icon index does not bind current P2 Authority", "authority_hash_mismatch"))
    expected = {
        item["visual_ref"]
        for slide in p2_manifest["slides"]
        for item in slide["visual_placeholders"]
        if item["role"] == "icon"
    }
    actual = [item["visual_ref"] for item in index["entries"]]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        failures.append(error("$.icon_asset_index.entries", "Icon entries must exactly cover P2 icon placeholders", "icon_set_mismatch"))
    for position, item in enumerate(index["entries"]):
        base = f"$.icon_asset_index.entries[{position}]"
        try:
            if item["status"] == "resolved_svg":
                record = load_json(_safe(index_path, item["resolution_record_path"]))
                validate_schema("production_icon_resolution", record, SCHEMA_DIR)
                manifest = load_json(_safe(index_path, item["asset_manifest_path"]))
                validate_schema("asset_manifest", manifest, SCHEMA_DIR)
                entries = [entry for entry in manifest["assets"] if entry["id"] == item["visual_ref"]]
                svg_path = _safe(index_path, item["sanitized_svg_path"])
                if (
                    record["visual_ref"] != item["visual_ref"]
                    or canonical_sha256(record) != item["resolution_record_sha256"]
                    or len(entries) != 1
                    or canonical_sha256(entries[0]) != item["asset_manifest_entry_sha256"]
                    or not svg_path.is_file()
                    or sha256_file(svg_path) != item["sanitized_svg_sha256"]
                    or entries[0]["sha256"] != item["sanitized_svg_sha256"]
                ):
                    failures.append(error(base, "Resolved SVG authority chain mismatch", "authority_hash_mismatch"))
            else:
                handoff = load_json(_safe(index_path, item["handoff_path"]))
                validate_schema("raster_handoff_pending", handoff, SCHEMA_DIR)
                if handoff["visual_ref"] != item["visual_ref"] or canonical_sha256(handoff) != item["handoff_sha256"]:
                    failures.append(error(base, "Raster Handoff authority chain mismatch", "authority_hash_mismatch"))
        except (OSError, ContractError, json.JSONDecodeError):
            failures.append(error(base, "Icon authority artifact is missing or invalid", "missing_authority"))
    if failures:
        raise ContractError(failures)
    return index


def load_visual_system_authority(
    *, p1_state_path: Path, deck_request_path: Path, approved_outline_path: Path, slide_content_dir: Path,
    p2_state_path: Path, wireframe_root: Path, icon_asset_index_path: Path,
) -> dict[str, Any]:
    p1_state = load_json(p1_state_path)
    validate_schema("content_plan_state", p1_state, SCHEMA_DIR)
    deck_request = load_json(deck_request_path)
    validate_schema("deck_request", deck_request, SCHEMA_DIR)
    p1 = load_markdown_authority(
        approved_outline_path=approved_outline_path, slide_content_dir=slide_content_dir, p1_state_path=p1_state_path,
    )
    p2_state = load_json(p2_state_path)
    validate_schema("markdown_wireframe_state", p2_state, SCHEMA_DIR)
    if p2_state["state"] != "p2_complete":
        raise ContractError([error("$.p2_state.state", "P3.2 requires p2_complete", "p2_not_complete")])
    manifest_path = wireframe_root / "wireframe-manifest.json"
    markdown_path = wireframe_root / "deck-wireframe.md"
    p2_manifest = load_json(manifest_path)
    validate_schema("markdown_wireframe_manifest", p2_manifest, SCHEMA_DIR)
    candidate_path = wireframe_root / "revisions" / f"r{p2_manifest['revision']:03d}" / "candidate.json"
    p2_candidate = load_json(candidate_path)
    validate_schema("markdown_wireframe_candidate", p2_candidate, SCHEMA_DIR)
    failures: list[dict[str, str]] = []
    deck_id = deck_request["deck_id"]
    documents = (p1_state, p1["approved_outline"], p1["projection_manifest"], p2_state, p2_manifest, p2_candidate)
    if any(item.get("deck_id") != deck_id for item in documents):
        failures.append(error("$", "P3.2 Authority Bundle contains cross-deck input", "deck_mismatch"))
    if p2_manifest["status"] != "accepted" or canonical_sha256(p2_manifest) != p2_state["current_artifacts"]["wireframe_manifest_sha256"]:
        failures.append(error("$.p2_manifest", "P2 Manifest is not the accepted State authority", "authority_hash_mismatch"))
    if not markdown_path.is_file() or sha256_bytes(markdown_path.read_bytes()) != p2_manifest["wireframe_sha256"]:
        failures.append(error("$.p2_manifest.wireframe_sha256", "P2 Markdown hash mismatch", "authority_hash_mismatch"))
    if canonical_sha256(p2_candidate) != p2_manifest["candidate_sha256"]:
        failures.append(error("$.p2_manifest.candidate_sha256", "P2 Candidate hash mismatch", "authority_hash_mismatch"))
    if deck_request["page_count"] != len(p2_manifest["slides"]):
        failures.append(error("$.deck_request.page_count", "Deck Request page count differs from P2", "slide_set_mismatch"))
    if failures:
        raise ContractError(failures)
    icon_index = validate_icon_asset_index(icon_asset_index_path, p2_manifest)
    bundle = {
        "deck_id": deck_id,
        "deck_request": deck_request,
        "p1_state": p1_state,
        "approved_outline": p1["approved_outline"],
        "projection_manifest": p1["projection_manifest"],
        "slide_contents": p1["slide_contents"],
        "p2_state": p2_state,
        "p2_manifest": p2_manifest,
        "p2_candidate": p2_candidate,
        "icon_asset_index": icon_index,
        "hashes": {
            "deck_request_sha256": canonical_sha256(deck_request),
            "approved_outline_sha256": canonical_sha256(p1["approved_outline"]),
            "slide_content_manifest_sha256": canonical_sha256(p1["projection_manifest"]),
            "p2_manifest_sha256": canonical_sha256(p2_manifest),
            "p3_icon_asset_index_sha256": canonical_sha256(icon_index),
        },
    }
    bundle["authority_bundle_sha256"] = canonical_sha256({"deck_id": deck_id, **bundle["hashes"]})
    return bundle


def _contrast(first: str, second: str) -> float:
    def luminance(value: str) -> float:
        channels = [int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        converted = [item / 12.92 if item <= .04045 else ((item + .055) / 1.055) ** 2.4 for item in channels]
        return .2126 * converted[0] + .7152 * converted[1] + .0722 * converted[2]
    a, b = luminance(first), luminance(second)
    return (max(a, b) + .05) / (min(a, b) + .05)


def validate_visual_system_candidate(candidate: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    validate_schema("deck_visual_system_candidate", candidate, SCHEMA_DIR)
    problems: list[tuple[str, str, str, bool]] = []
    if candidate["deck_id"] != bundle["deck_id"]:
        problems.append(("deck_mismatch", "$.deck_id", "Candidate belongs to another Deck", True))
    hard, soft = candidate["hard_constraints"], candidate["soft_design_guidance"]
    request = bundle["deck_request"]
    expected_canvas = (1600, 900) if request["output_ratio"] == "16:9" else (1200, 900)
    if hard["output_ratio"] != request["output_ratio"] or (hard["canvas"]["width_px"], hard["canvas"]["height_px"]) != expected_canvas:
        problems.append(("ratio_mismatch", "$.hard_constraints.output_ratio", "Hard canvas must match Deck Request", True))
    if any(value > 2000 for value in hard["safe_area"].values()):
        problems.append(("safe_area_too_large", "$.hard_constraints.safe_area", "Safe area cannot exceed 20 percent", False))
    palette = hard["palette"]
    if len(set(palette.values())) < 4:
        problems.append(("palette_insufficient", "$.hard_constraints.palette", "Palette requires at least four distinct colors", False))
    if _contrast(palette["text_primary"], palette["background"]) < 4.5:
        problems.append(("contrast_failure", "$.hard_constraints.palette.text_primary", "Primary text contrast must be at least 4.5", False))
    installed = installed_font_names()
    for token, font in hard["typography"].items():
        if font["minimum_size_pt"] > font["size_pt"]:
            problems.append(("font_size_order", f"$.hard_constraints.typography.{token}", "Minimum size cannot exceed preferred size", False))
        if installed and _normalize_font(font["family"]) not in installed and _normalize_font(font["fallback_family"]) not in installed:
            problems.append(("font_unavailable", f"$.hard_constraints.typography.{token}", "Primary and fallback fonts are unavailable", False))
    roles = [page["role"] for page in bundle["approved_outline"]["pages"]]
    mappings = [item["slide_role"] for item in soft["template_families"]]
    if len(mappings) != len(set(mappings)) or set(mappings) != set(roles):
        problems.append(("template_role_coverage", "$.soft_design_guidance.template_families", "Soft template guidance must cover every unique slide role exactly once", False))
    encoded = json.dumps(soft, ensure_ascii=False)
    if FORBIDDEN_GUIDANCE.search(encoded):
        problems.append(("unsafe_soft_guidance", "$.soft_design_guidance", "Soft guidance contains path, URL, SVG, or hash", True))
    for forbidden in ("bbox", "normalized_bbox", "fixed_x", "fixed_y", "fixed_width", "fixed_height"):
        if f'"{forbidden}"' in encoded:
            problems.append(("soft_became_hard", "$.soft_design_guidance", "Soft guidance cannot prescribe fixed geometry", True))
    return [
        {"issue_id": f"P32-{index:03d}", "classification": "blocking_authority_error" if blocking else "correctable_contract_error", "code": code, "path": path, "message": message, "correctable": not blocking}
        for index, (code, path, message, blocking) in enumerate(problems, 1)
    ]


def build_validation_report(candidate: dict[str, Any], bundle: dict[str, Any], *, report_id: str, validated_at_utc: str) -> dict[str, Any]:
    issues = validate_visual_system_candidate(candidate, bundle)
    result = {"schema_version":"1.0","artifact_type":"deck_visual_system_validation_report","report_id":report_id,"deck_id":candidate["deck_id"],"candidate_sha256":canonical_sha256(candidate),"status":"blocking" if any(not item["correctable"] for item in issues) else ("correctable" if issues else "pass"),"issues":issues,"validated_at_utc":validated_at_utc}
    validate_schema("deck_visual_system_validation_report", result, SCHEMA_DIR)
    return result


def freeze_visual_system(candidate: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    issues = validate_visual_system_candidate(candidate, bundle)
    if issues:
        raise ContractError([error(item["path"], item["message"], item["code"]) for item in issues])
    result = {"schema_version":"1.0","canonicalization_version":"p1-rfc8785-nfc-1","artifact_type":"deck_visual_system","deck_id":candidate["deck_id"],"revision":candidate["revision"],"parent_sha256":candidate["parent_sha256"],"candidate_sha256":canonical_sha256(candidate),**bundle["hashes"],"hard_constraints":candidate["hard_constraints"],"soft_design_guidance":candidate["soft_design_guidance"],"status":"frozen"}
    validate_schema("deck_visual_system", result, SCHEMA_DIR)
    return result
