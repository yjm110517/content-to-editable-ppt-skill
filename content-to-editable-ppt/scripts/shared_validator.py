from __future__ import annotations

from pathlib import Path
from typing import Any

from schema_utils import ContractError, cross_validate, is_safe_relative_path, validate_build_ready, validate_schema, validate_semantics


PROFILES = {"candidate", "post_patch", "pre_build", "final_delivery"}


def _failure(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def _core(documents: dict[str, dict[str, Any]]) -> None:
    failures: list[dict[str, str]] = []
    layout = documents.get("layout")
    crops = documents.get("crops")
    if layout:
        ids: set[str] = set()
        content_refs: set[tuple[str, int]] = set()
        for index, element in enumerate(layout["elements"]):
            base = f"$.elements[{index}]"
            if element["id"] in ids:
                failures.append(_failure(base + ".id", "duplicate_id", "element id must be unique"))
            ids.add(element["id"])
            if element["type"] == "text" and layout["schema_version"] in {"1.4", "1.5"}:
                for field in ("content_ref", "segment_order", "joiner"):
                    if field not in element:
                        failures.append(_failure(base + "." + field, "content_identity", "layout 1.4 text requires content identity fields"))
                if "content_ref" in element and "segment_order" in element:
                    identity = (element["content_ref"], element["segment_order"])
                    if identity in content_refs:
                        failures.append(_failure(base, "content_identity", "content_ref and segment_order must be unique"))
                    content_refs.add(identity)
            if element["type"] == "line":
                for field in ("from_id", "to_id"):
                    if field in element and element[field] not in ids and not any(item.get("id") == element[field] for item in layout["elements"]):
                        failures.append(_failure(base + "." + field, "unknown_reference", "connector endpoint does not exist"))
    if crops:
        source_width = layout["source"]["width_px"] if layout else None
        source_height = layout["source"]["height_px"] if layout else None
        for index, crop in enumerate(crops["assets"]):
            base = f"$.assets[{index}]"
            left, top, right, bottom = crop["box_px"]
            if right <= left or bottom <= top:
                failures.append(_failure(base + ".box_px", "invalid_crop_box", "box_px uses [left, top, right, bottom] with positive area"))
            if source_width is not None and (right > source_width or bottom > source_height):
                failures.append(_failure(base + ".box_px", "crop_out_of_bounds", "crop exceeds source dimensions"))
            if crop["remove_background"]:
                failures.append(_failure(base + ".remove_background", "unsupported_operation", "automatic background removal is not supported"))
            if not is_safe_relative_path(crop["output"], filename_only=True):
                failures.append(_failure(base + ".output", "unsafe_path", "crop output must be a safe filename"))
    if failures:
        raise ContractError(failures)


def validate_documents(
    documents: dict[str, dict[str, Any]],
    paths: dict[str, Path],
    *,
    profile: str,
    schema_dir: Path,
) -> None:
    if profile not in PROFILES:
        raise ValueError(f"unknown validation profile: {profile}")
    for kind, document in documents.items():
        validate_schema(kind, document, schema_dir)
    _core(documents)
    for kind, document in documents.items():
        validate_semantics(kind, document)
    cross_validate(documents)
    if profile == "pre_build" and "asset_manifest" in documents:
        validate_build_ready(paths["asset_manifest"], documents["asset_manifest"])
