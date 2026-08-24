from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from schema_utils import ContractError, error


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_once(path: Path, value: dict[str, Any]) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() == data:
            return
        raise ContractError([error(str(path), "preview artifact already exists with different bytes", "overwrite_forbidden")])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _copy_once(source: Path, target: Path) -> None:
    if target.exists():
        if sha256_file(source) == sha256_file(target):
            return
        raise ContractError([error(str(target), "preview asset already exists with different bytes", "overwrite_forbidden")])
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _inches(box: dict[str, int]) -> dict[str, float]:
    return {
        "x": round(box["x"] * 13.333 / 10000, 4),
        "y": round(box["y"] * 7.5 / 10000, 4),
        "w": round(box["w"] * 13.333 / 10000, 4),
        "h": round(box["h"] * 7.5 / 10000, 4),
    }


def project_preview(
    *,
    deck_id: str,
    slide_id: str,
    content: dict[str, Any],
    element_map: dict[str, Any],
    visual_system: dict[str, Any],
    footprints: dict[str, Any],
    raw_layer: Path,
    output_dir: Path,
) -> dict[str, Path]:
    if content["slide_id"] != slide_id or element_map["slide_id"] != slide_id:
        raise ContractError([error("$.slide_id", "preview projection inputs belong to different slides", "deck_mismatch")])
    text_by_ref = {content["title"]["content_ref"]: content["title"]["text"]}
    text_by_ref.update({item["content_ref"]: item["text"] for item in content["content_blocks"]})
    footprint_by_ref = {item["content_ref"]: item for item in footprints["entries"] if item["slide_id"] == slide_id}
    map_by_ref = {item["source_ref"]: item for item in element_map["elements"] if item["source_ref"] and item["reconstruction_class"] == "native_text"}
    missing = set(text_by_ref) - set(map_by_ref)
    if missing:
        raise ContractError([error("$.element_map", f"native text map is missing Content Refs: {sorted(missing)}", "element_intent_mismatch")])
    if any(item["reconstruction_class"] == "native_chart" for item in element_map["elements"]):
        raise ContractError([error("$.element_map", "native chart requires a separately frozen PowerPoint Chart Spec", "chart_authority_missing")])
    unresolved = [item["source_ref"] for item in element_map["elements"] if item["reconstruction_class"] == "sanitized_svg"]
    if unresolved:
        raise ContractError([error("$.element_map", "Preview projector requires a resolved SVG asset manifest for sanitized SVG", "missing_authority")])
    raw_target = output_dir / "assets" / "raw-layer.png"
    source_target = output_dir / "source.png"
    _copy_once(raw_layer, raw_target)
    _copy_once(raw_layer, source_target)
    width, height = 1600, 900
    asset_manifest = {
        "schema_version": "1.3",
        "assets": [{"id": "RAW-LAYER", "type": "png", "path": "assets/raw-layer.png", "source": "agent-generated", "width_px": width, "height_px": height, "size_bytes": raw_target.stat().st_size, "sha256": sha256_file(raw_target), "recolorable": False, "contains_text": False, "text_editability_exempt": False, "security_status": "passed"}],
    }
    palette = visual_system["hard_constraints"]["palette"]
    elements: list[dict[str, Any]] = [{"id": "raw-layer", "type": "image", "x": 0, "y": 0, "w": 13.333, "h": 7.5, "z_index": 0, "editable": False, "asset_id": "RAW-LAYER", "fit": "stretch", "preserve_aspect_ratio": False, "contains_text": False, "alt_text": "Preview-only generated visual layer"}]
    for content_ref, text in text_by_ref.items():
        mapping = map_by_ref[content_ref]
        footprint = footprint_by_ref.get(content_ref)
        if footprint is None:
            raise ContractError([error("$.text_footprints", f"Text Footprint is missing {content_ref}", "text_footprint_blocking")])
        coords = _inches(mapping["normalized_bbox"])
        is_title = content_ref.endswith("-TITLE")
        elements.append({
            "id": mapping["element_id"], "type": "text", **coords, "z_index": mapping["z_index"], "editable": True,
            "text": text, "font_face": footprint["font_family"], "font_size_pt": footprint["font_size_pt"], "bold": is_title,
            "color": palette["text_primary"] if is_title else palette["text_secondary"], "margin_in": 0,
            "line_spacing_multiple": footprint["line_height_milli"] / 1000, "fit": "shrink", "language": "zh-CN", "content_ref": content_ref,
        })
    request = {
        "schema_version": "1.3", "task_id": f"{deck_id}-{slide_id}-preview", "topic": "P3.3 Preview", "source_image": "source.png", "output_ratio": "16:9", "typography_interaction": "default",
        "typography": {"title_font": visual_system["hard_constraints"]["typography"]["title"]["family"], "title_size_pt": visual_system["hard_constraints"]["typography"]["title"]["size_pt"], "body_font": visual_system["hard_constraints"]["typography"]["body"]["family"], "body_size_pt": visual_system["hard_constraints"]["typography"]["body"]["size_pt"]},
        "editability_policy": "text-and-structure", "user_requirements": [], "review_policy": {"max_iterations": 1, "pass_score": 90, "warning_floor_score": 80, "min_content_accuracy": 100, "required_editability_score": 100, "critical_policy": "by_recoverability"},
    }
    layout = {"schema_version": "1.3", "request": "request.json", "source": {"image": "source.png", "width_px": width, "height_px": height}, "slide": {"width_in": 13.333, "height_in": 7.5, "background": palette["background"]}, "metadata": {"topic": "P3.3 Preview", "iteration": 1, "typography_interaction": "default"}, "asset_manifest": "asset_manifest.json", "styles": {}, "elements": sorted(elements, key=lambda item: item["z_index"])}
    request_path, manifest_path, layout_path = output_dir / "request.json", output_dir / "asset_manifest.json", output_dir / "layout.json"
    _write_once(request_path, request)
    _write_once(manifest_path, asset_manifest)
    _write_once(layout_path, layout)
    return {"request": request_path, "asset_manifest": manifest_path, "layout": layout_path, "asset_dir": output_dir / "assets", "raw": raw_target}
