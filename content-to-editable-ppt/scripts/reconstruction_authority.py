from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Iterable

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, is_safe_relative_path, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_file(path: Path, json_path: str) -> Path:
    if not path.is_file():
        raise ContractError([error(json_path, "required authority file is missing", "missing_authority")])
    return path.resolve()


def _safe_child(root: Path, relative: str, json_path: str) -> Path:
    if not is_safe_relative_path(relative):
        raise ContractError([error(json_path, "path must be a safe relative path", "path_escape")])
    target = (root.resolve() / Path(*relative.split("/"))).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ContractError([error(json_path, "path escapes authority root", "path_escape")]) from exc
    return _require_file(target, json_path)


def _page_root(page_roots: dict[str, Path], slide_id: str) -> Path:
    root = page_roots.get(slide_id)
    if root is None:
        raise ContractError([error("$.page_roots", f"missing page root for {slide_id}", "missing_authority")])
    return root.resolve()


def load_reconstruction_authority(
    *,
    p3_state_path: Path,
    approved_manifest_path: Path,
    page_roots: dict[str, Path],
) -> dict[str, Any]:
    state = load_json(_require_file(p3_state_path, "$.p3_state"))
    manifest = load_json(_require_file(approved_manifest_path, "$.approved_manifest"))
    validate_schema("design_preview_state", state, SCHEMA_DIR)
    validate_schema("approved_design_preview_manifest", manifest, SCHEMA_DIR)
    failures: list[dict[str, str]] = []
    if state["state"] != "p3_3_complete":
        failures.append(error("$.p3_state.state", "P4 requires p3_3_complete", "authority_state_mismatch"))
    if manifest["status"] != "approved":
        failures.append(error("$.approved_manifest.status", "P4 requires approved previews", "authority_state_mismatch"))
    if state["deck_id"] != manifest["deck_id"]:
        failures.append(error("$.approved_manifest.deck_id", "deck id differs from P3.3 state", "authority_deck_mismatch"))
    manifest_sha = canonical_sha256(manifest)
    frozen = state.get("current_artifacts", {}).get("approved_design_preview_manifest_sha256")
    if not frozen:
        failures.append(error("$.p3_state.current_artifacts.approved_design_preview_manifest_sha256", "frozen approved manifest hash is required", "missing_authority"))
    elif frozen != manifest_sha:
        failures.append(error("$.p3_state.current_artifacts.approved_design_preview_manifest_sha256", "approved manifest hash mismatch", "authority_hash_mismatch"))
    if failures:
        raise ContractError(failures)

    pages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, entry in enumerate(manifest["previews"]):
        slide_id = entry["slide_id"]
        if slide_id in seen:
            failures.append(error(f"$.approved_manifest.previews[{index}].slide_id", "duplicate slide id", "authority_duplicate"))
            continue
        seen.add(slide_id)
        root = _page_root(page_roots, slide_id)
        preview_record_path = _require_file(root / "final-design-preview-record.json", f"$.pages.{slide_id}.preview_record")
        element_map_path = _require_file(root / "design-element-map.json", f"$.pages.{slide_id}.element_map")
        compatibility_path = _require_file(root / "reconstruction-compatibility-report.json", f"$.pages.{slide_id}.compatibility_report")
        preview_record = load_json(preview_record_path)
        element_map = load_json(element_map_path)
        compatibility = load_json(compatibility_path)
        validate_schema("final_design_preview_record", preview_record, SCHEMA_DIR)
        validate_schema("design_element_map", element_map, SCHEMA_DIR)
        validate_schema("reconstruction_compatibility_report", compatibility, SCHEMA_DIR)
        if canonical_sha256(preview_record) != entry["final_preview_record_sha256"]:
            failures.append(error(f"$.approved_manifest.previews[{index}].final_preview_record_sha256", "preview record hash mismatch", "authority_hash_mismatch"))
        preview_image = _safe_child(root, preview_record["final_preview_path"], f"$.pages.{slide_id}.final_preview_path")
        if file_sha256(preview_image) != entry["final_preview_sha256"] or preview_record["final_preview_sha256"] != entry["final_preview_sha256"]:
            failures.append(error(f"$.approved_manifest.previews[{index}].final_preview_sha256", "preview image hash mismatch", "authority_hash_mismatch"))
        if preview_record["element_map_sha256"] != canonical_sha256(element_map):
            failures.append(error(f"$.pages.{slide_id}.element_map", "element map hash mismatch", "authority_hash_mismatch"))
        if preview_record["compatibility_report_sha256"] != canonical_sha256(compatibility):
            failures.append(error(f"$.pages.{slide_id}.compatibility_report", "compatibility report hash mismatch", "authority_hash_mismatch"))
        if compatibility["status"] != "pass" or compatibility["element_map_sha256"] != canonical_sha256(element_map):
            failures.append(error(f"$.pages.{slide_id}.compatibility_report", "current element map is not reconstruction-compatible", "reconstruction_incompatible"))
        for document in (preview_record, element_map, compatibility):
            if document["deck_id"] != manifest["deck_id"] or document["slide_id"] != slide_id:
                failures.append(error(f"$.pages.{slide_id}", "page authority identity mismatch", "authority_deck_mismatch"))
        pages.append({"slide_id": slide_id, "order": entry["order"], "root": root, "preview_record": preview_record, "preview_image": preview_image, "element_map": element_map, "compatibility": compatibility})
    if failures:
        raise ContractError(failures)
    if [item["order"] for item in pages] != list(range(1, len(pages) + 1)):
        raise ContractError([error("$.approved_manifest.previews", "page order must be contiguous", "authority_order_mismatch")])
    return {"deck_id": manifest["deck_id"], "state": state, "manifest": manifest, "manifest_sha256": manifest_sha, "pages": pages}


def build_reconstruction_asset_manifest(
    *, deck_id: str, evidence_root: Path, record_paths: Iterable[Path]
) -> dict[str, Any]:
    root = evidence_root.resolve()
    assets: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    seen_refs: set[str] = set()
    evidence_inputs: list[dict[str, str]] = []
    for index, record_path in enumerate(record_paths):
        record_path = _require_file(record_path, f"$.records[{index}]")
        record = load_json(record_path)
        validate_schema("extracted_visual_asset_record", record, SCHEMA_DIR)
        if record["deck_id"] != deck_id or record["status"] != "approved":
            failures.append(error(f"$.records[{index}]", "asset record is not approved for current deck", "authority_deck_mismatch"))
            continue
        asset_ref = record["visual_ref"]
        if asset_ref in seen_refs:
            failures.append(error(f"$.records[{index}].visual_ref", "duplicate asset ref", "authority_duplicate"))
            continue
        seen_refs.add(asset_ref)
        output_name = record["output_path"]
        candidates = [record_path.parent / output_name]
        candidates.extend(root.glob(f"**/{Path(output_name).name}"))
        actual = next((candidate.resolve() for candidate in candidates if candidate.is_file() and file_sha256(candidate) == record["output_png_sha256"]), None)
        if actual is None:
            failures.append(error(f"$.records[{index}].output_path", "approved extracted asset bytes were not found", "missing_authority"))
            continue
        try:
            relative = actual.relative_to(root).as_posix()
        except ValueError:
            failures.append(error(f"$.records[{index}].output_path", "approved asset is outside evidence root", "path_escape"))
            continue
        record_relative = record_path.relative_to(root).as_posix() if record_path.is_relative_to(root) else record_path.name
        evidence_inputs.append({"record_path": record_relative, "record_sha256": canonical_sha256(record)})
        assets.append({"asset_ref": asset_ref, "slide_id": record["slide_id"], "element_id": record["element_id"], "record_sha256": canonical_sha256(record), "path": relative, "sha256": record["output_png_sha256"], "media_type": "image/png", "status": "approved"})
    if failures:
        raise ContractError(failures)
    assets.sort(key=lambda item: (item["slide_id"], item["asset_ref"]))
    result = {"schema_version": "1.0", "artifact_type": "reconstruction_asset_manifest", "deck_id": deck_id, "evidence_root_sha256": canonical_sha256(evidence_inputs), "assets": assets, "status": "validated"}
    validate_schema("reconstruction_asset_manifest", result, SCHEMA_DIR)
    return result


def _content_by_ref(content: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {content["title"]["content_ref"]: {"text": content["title"]["text"], "role": "title"}}
    for block in content["content_blocks"]:
        result[block["content_ref"]] = {"text": block["text"], "role": "body"}
    return result


def _palette_token(value: str, palette: dict[str, str], *, fallback: str) -> str:
    normalized = value.replace("-soft", "")
    return palette.get(normalized, palette.get(value, fallback))


def _asset_for(asset_manifest: dict[str, Any], slide_id: str, source_ref: str | None) -> dict[str, Any] | None:
    matches = [item for item in asset_manifest["assets"] if item["slide_id"] == slide_id and item["asset_ref"] == source_ref]
    return matches[0] if len(matches) == 1 else None


def build_seed_view(
    *,
    page: dict[str, Any],
    approved_content: dict[str, Any],
    visual_system: dict[str, Any],
    text_footprints: dict[str, Any],
    asset_manifest: dict[str, Any],
    chart_specs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validate_schema("approved_slide_content", approved_content, SCHEMA_DIR)
    validate_schema("deck_visual_system", visual_system, SCHEMA_DIR)
    validate_schema("text_footprint_manifest", text_footprints, SCHEMA_DIR)
    validate_schema("reconstruction_asset_manifest", asset_manifest, SCHEMA_DIR)
    chart_specs = chart_specs or {}
    slide_id = page["slide_id"]
    deck_id = page["preview_record"]["deck_id"]
    failures: list[dict[str, str]] = []
    if approved_content["deck_id"] != deck_id or approved_content["slide_id"] != slide_id:
        failures.append(error("$.approved_content", "content authority identity mismatch", "authority_deck_mismatch"))
    if visual_system["deck_id"] != deck_id or text_footprints["deck_id"] != deck_id or asset_manifest["deck_id"] != deck_id:
        failures.append(error("$.authority", "P4 authority artifacts belong to another deck", "authority_deck_mismatch"))
    content = _content_by_ref(approved_content)
    footprints = {(item["slide_id"], item["content_ref"]): item for item in text_footprints["entries"]}
    hard = visual_system["hard_constraints"]
    palette = hard["palette"]
    typography = hard["typography"]
    seeds: list[dict[str, Any]] = []
    for index, item in enumerate(sorted(page["element_map"]["elements"], key=lambda element: (element["z_index"], element["element_id"]))):
        kind = item["reconstruction_class"]
        source_ref = item.get("source_ref")
        implementation: dict[str, Any]
        if kind == "native_text":
            authority = content.get(source_ref or "")
            footprint = footprints.get((slide_id, source_ref))
            if authority is None or footprint is None:
                failures.append(error(f"$.elements[{index}]", "native text authority or footprint is missing", "reconstruction_seed_incomplete"))
                continue
            token = footprint["font_token"]
            font = typography[token]
            if hashlib.sha256(authority["text"].encode("utf-8")).hexdigest() != footprint["text_sha256"]:
                failures.append(error(f"$.elements[{index}].source_ref", "text footprint does not bind current authority text", "authority_hash_mismatch"))
                continue
            implementation = {"content_ref": source_ref, "text": authority["text"], "text_sha256": footprint["text_sha256"], "font_family": font["family"], "fallback_family": font["fallback_family"], "font_size_pt": font["size_pt"], "minimum_font_size_pt": font["minimum_size_pt"], "weight": font["weight"], "alignment": "left", "vertical_alignment": "top", "margin_milli": 0, "line_spacing_milli": font["line_height_milli"], "wrap_policy": "powerpoint_wrap", "max_lines": footprint["max_lines"], "color": palette["text_primary"]}
        elif kind == "native_shape":
            required = ["shape_kind", "fill", "border", "corner_radius", "opacity", "shadow_class"]
            missing = [field for field in required if field not in item]
            if missing:
                failures.append(error(f"$.elements[{index}]", f"native shape seed is missing: {', '.join(missing)}", "reconstruction_seed_incomplete"))
                continue
            implementation = {"shape_kind": item["shape_kind"], "style_seed": {"fill_token": item["fill"], "fill_color": _palette_token(item["fill"], palette, fallback=palette["surface"]), "border_token": item["border"], "border_color": _palette_token(item["border"], palette, fallback=palette["primary"]), "radius_token": f"radius_{item['corner_radius']}", "corner_radius": item["corner_radius"], "shadow_token": item["shadow_class"], "opacity_milli": item["opacity"]}}
        elif kind == "native_chart":
            chart = chart_specs.get(source_ref or "")
            if chart is None:
                failures.append(error(f"$.elements[{index}].source_ref", "frozen PowerPoint Chart Spec is missing", "reconstruction_seed_incomplete"))
                continue
            validate_schema("powerpoint_chart_spec", chart, SCHEMA_DIR)
            implementation = {"chart_spec": chart, "chart_spec_sha256": canonical_sha256(chart)}
        elif kind in {"sanitized_svg", "reusable_raster", "generated_foreground"}:
            asset = _asset_for(asset_manifest, slide_id, source_ref)
            if asset is None:
                failures.append(error(f"$.elements[{index}].source_ref", "approved asset is missing", "reconstruction_seed_incomplete"))
                continue
            implementation = {"asset_ref": asset["asset_ref"], "approved_record_sha256": asset["record_sha256"], "actual_asset_sha256": asset["sha256"], "asset_path": asset["path"], "media_type": asset["media_type"], "fit": "contain", "crop": None, "layer_role": "foreground" if kind == "generated_foreground" else "content"}
        elif kind == "generated_background":
            if item["p4_strategy"] == "reuse_background_raster":
                asset = _asset_for(asset_manifest, slide_id, source_ref)
                if asset is None:
                    failures.append(error(f"$.elements[{index}]", "approved background raster is missing", "reconstruction_seed_incomplete"))
                    continue
                implementation = {"background_strategy": "approved_background_raster", "asset_ref": asset["asset_ref"], "approved_record_sha256": asset["record_sha256"], "actual_asset_sha256": asset["sha256"], "asset_path": asset["path"]}
            elif item["p4_strategy"] == "rebuild_background_from_style_tokens":
                implementation = {"background_strategy": "reconstructable_background", "fill_color": palette["background"], "surface_color": palette["surface"], "primary_color": palette["primary"], "accent_color": palette["accent"]}
            else:
                failures.append(error(f"$.elements[{index}].p4_strategy", "background strategy is not frozen", "reconstruction_seed_incomplete"))
                continue
        elif kind == "decorative_approximation":
            implementation = {"approximation_kind": "soft_blob", "fill_color": palette["primary"], "accent_color": palette["accent"], "opacity_milli": 180}
        else:
            failures.append(error(f"$.elements[{index}].reconstruction_class", "unsupported reconstruction seed class", "reconstruction_seed_incomplete"))
            continue
        seed = {"schema_version": "1.0", "artifact_type": "reconstruction_seed", "deck_id": deck_id, "slide_id": slide_id, "element_id": item["element_id"], "source_ref": source_ref, "reconstruction_class": kind, "p4_strategy": item["p4_strategy"], "fidelity_priority": item["fidelity_priority"], "editable_required": item["editable_required"], "normalized_bbox": item["normalized_bbox"], "z_index": item["z_index"], "relationship_refs": item["relationship_refs"], "implementation": implementation}
        seed["seed_input_sha256"] = canonical_sha256({key: value for key, value in seed.items() if key != "seed_input_sha256"})
        validate_schema("reconstruction_seed", seed, SCHEMA_DIR)
        seeds.append(seed)
    if failures:
        raise ContractError(failures)
    result = {"schema_version": "1.0", "artifact_type": "reconstruction_seed_view", "deck_id": deck_id, "slide_id": slide_id, "approved_preview_sha256": page["preview_record"]["final_preview_sha256"], "element_map_sha256": canonical_sha256(page["element_map"]), "compatibility_report_sha256": canonical_sha256(page["compatibility"]), "content_authority_sha256": canonical_sha256(approved_content), "asset_manifest_sha256": canonical_sha256(asset_manifest), "visual_system_sha256": canonical_sha256(visual_system), "text_footprint_manifest_sha256": canonical_sha256(text_footprints), "seeds": seeds, "status": "complete"}
    validate_schema("reconstruction_seed_view", result, SCHEMA_DIR)
    return result


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise ContractError([error("$.output", "output already exists", "overwrite_forbidden")])
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(f".{path.name}.tmp")
    staged.write_text(__import__("json").dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    os.replace(staged, path)
