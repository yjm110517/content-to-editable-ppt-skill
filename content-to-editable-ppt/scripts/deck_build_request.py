from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image

from asset_common import AssetError
from sanitize_svg import sanitize_bytes
from schema_utils import ContractError, error, is_safe_relative_path, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
DIMENSIONS = {
    "16:9": {"width_in": 13.333, "height_in": 7.5, "width_px": 1600, "height_px": 900},
    "4:3": {"width_in": 10.0, "height_in": 7.5, "width_px": 1200, "height_px": 900},
}
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MEDIA_TYPES = {"image/png": ("png", ".png", "PNG"), "image/jpeg": ("jpeg", ".jpg", "JPEG"), "image/svg+xml": ("svg", ".svg", "SVG")}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_text(element: dict[str, Any]) -> str:
    if "text" in element:
        value = element["text"]
    else:
        parts: list[str] = []
        for run in element.get("runs", []):
            parts.append(run["text"])
            if run.get("break_line"):
                parts.append("\n")
        value = "".join(parts)
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def _intersects(left: dict[str, Any], right: dict[str, Any], *, tolerance: float = 1e-9) -> bool:
    return (
        min(left["x"] + left["w"], right["x"] + right["w"]) - max(left["x"], right["x"]) > tolerance
        and min(left["y"] + left["h"], right["y"] + right["h"]) - max(left["y"], right["y"]) > tolerance
    )


def _resolved_text_style(element: dict[str, Any], style: dict[str, Any], run: dict[str, Any] | None = None) -> tuple[Any, Any, Any]:
    current = run or {}
    return (
        current.get("font_face", element.get("font_face", style.get("font_face"))),
        current.get("font_size_pt", element.get("font_size_pt", style.get("font_size_pt"))),
        current.get("color", element.get("color", style.get("color"))),
    )


def validate_request(document: dict[str, Any], schema_dir: Path = SCHEMA_DIR) -> dict[str, Any]:
    validate_schema("deck_build_request", document, schema_dir)
    failures: list[dict[str, str]] = []
    output_name = document["output_name"]
    if output_name.upper().split(".", 1)[0] in WINDOWS_RESERVED or output_name.endswith((" ", ".")):
        failures.append(error("$.output_name", "output_name is reserved or unsafe", "unsafe_output_name"))
    slides = document["slides"]
    orders = [slide["order"] for slide in slides]
    if len(set(orders)) != len(orders) or sorted(orders) != list(range(1, len(slides) + 1)):
        failures.append(error("$.slides", "slide order must be unique and contiguous from 1", "invalid_slide_order"))
    slide_ids = [slide["slide_id"] for slide in slides]
    if len(set(slide_ids)) != len(slide_ids):
        failures.append(error("$.slides", "slide_id must be unique", "duplicate_slide_id"))
    asset_ids = [item["asset_id"] for item in document["assets"]]
    if len(set(asset_ids)) != len(asset_ids):
        failures.append(error("$.assets", "asset_id must be unique", "duplicate_asset_id"))
    known_assets = set(asset_ids)
    styles = document["styles"]
    dimensions = DIMENSIONS[document["output_ratio"]]
    for slide_index, slide in enumerate(slides):
        base = f"$.slides[{slide_index}]"
        elements = slide["elements"]
        ids = [item["id"] for item in elements]
        if len(set(ids)) != len(ids):
            failures.append(error(base + ".elements", "element id must be unique within a slide", "duplicate_element_id"))
        known = set(ids)
        text_boxes: list[tuple[str, dict[str, Any]]] = []
        image_boxes: list[tuple[str, dict[str, Any]]] = []
        for element_index, element in enumerate(elements):
            path = f"{base}.elements[{element_index}]"
            if element.get("style_ref") and element["style_ref"] not in styles:
                failures.append(error(path + ".style_ref", "unknown style_ref", "unknown_style"))
            if element["type"] != "line" and (element["w"] <= 0 or element["h"] <= 0):
                failures.append(error(path, "non-line elements require positive width and height", "invalid_geometry"))
            if element["type"] == "line" and element["w"] <= 0 and element["h"] <= 0:
                failures.append(error(path, "line width and height cannot both be zero", "invalid_geometry"))
            if element["x"] + element["w"] > dimensions["width_in"] + 1e-6 or element["y"] + element["h"] > dimensions["height_in"] + 1e-6:
                failures.append(error(path, "element exceeds slide bounds", "geometry_out_of_bounds"))
            style = styles.get(element.get("style_ref", ""), {})
            if element["type"] == "text":
                if not element.get("content_ref"):
                    failures.append(error(path + ".content_ref", "native text requires content_ref", "missing_content_ref"))
                if not normalized_text(element).strip():
                    failures.append(error(path, "native text cannot be empty", "empty_text"))
                runs = element.get("runs") or [None]
                for run_index, run in enumerate(runs):
                    if any(value in (None, "") for value in _resolved_text_style(element, style, run)):
                        failures.append(error(f"{path}.runs[{run_index}]", "font_face, font_size_pt, and color must resolve", "unresolved_typography"))
                text_boxes.append((element["id"], element))
            elif element["type"] == "image":
                if element["asset_id"] not in known_assets:
                    failures.append(error(path + ".asset_id", "unknown asset_id", "unknown_asset"))
                image_boxes.append((element["id"], element))
            elif element["type"] == "line":
                for field in ("from_id", "to_id"):
                    if element.get(field) and element[field] not in known:
                        failures.append(error(path + f".{field}", f"unknown same-slide element: {element[field]}", "unknown_connector_target"))
        for image_id, image in image_boxes:
            for text_id, text in text_boxes:
                if _intersects(image, text):
                    failures.append(error(base + ".elements", f"image {image_id} overlaps text {text_id}", "image_text_overlap"))
        if len(elements) == 1 and elements[0]["type"] == "image":
            failures.append(error(base + ".elements", "a slide cannot be a single raster image", "full_slide_raster_substitution"))
    for index, asset in enumerate(document["assets"]):
        path = f"$.assets[{index}]"
        if not is_safe_relative_path(asset["path"]):
            failures.append(error(path + ".path", "asset path must be a safe POSIX relative path", "path_escape"))
        if asset["contains_text"] and not asset["text_editability_exempt"]:
            failures.append(error(path, "text-bearing assets require an editability exemption", "text_editability_violation"))
    if failures:
        raise ContractError(failures)
    return document


def load_request(path: Path, schema_dir: Path = SCHEMA_DIR) -> dict[str, Any]:
    if not path.is_file():
        raise AssetError("deck build request is missing", path=str(path), code="missing_input", exit_code=3)
    return validate_request(load_json(path), schema_dir)


def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & flag)


def _resolve_asset(root: Path, relative: str) -> Path:
    if not is_safe_relative_path(relative):
        raise AssetError("asset path must be a safe POSIX relative path", path=relative, code="path_escape")
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.exists() and _is_reparse(current):
            raise AssetError("asset path contains a symlink or reparse point", path=relative, code="path_escape")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise AssetError("asset path is missing or escapes asset-root", path=relative, code="path_escape", exit_code=3) from exc
    if not resolved.is_file():
        raise AssetError("asset must be a regular file", path=relative, code="invalid_asset")
    return resolved


def stage_assets(document: dict[str, Any], asset_root: Path | None, output_dir: Path) -> list[dict[str, Any]]:
    assets = document["assets"]
    if assets and asset_root is None:
        raise AssetError("--asset-root is required when assets are present", path="--asset-root", code="cli_error", exit_code=2)
    if output_dir.exists():
        raise AssetError("staged asset directory already exists", path=str(output_dir), code="output_collision", exit_code=9)
    if not assets:
        output_dir.mkdir(parents=True)
        return []
    assert asset_root is not None
    try:
        root = asset_root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise AssetError("asset-root does not exist", path=str(asset_root), code="missing_input", exit_code=3) from exc
    if not root.is_dir() or _is_reparse(root):
        raise AssetError("asset-root must be a real directory", path=str(asset_root), code="path_escape")
    output_dir.mkdir(parents=True)
    staged: list[dict[str, Any]] = []
    for item in assets:
        source = _resolve_asset(root, item["path"])
        source_hash = sha256_file(source)
        if source_hash != item["sha256"]:
            raise AssetError("asset SHA-256 mismatch", path=item["path"], code="hash_conflict", exit_code=9)
        kind, extension, expected_format = MEDIA_TYPES[item["media_type"]]
        destination = output_dir / f"{item['asset_id']}{extension}"
        width_px = height_px = None
        view_box = None
        if kind == "svg":
            sanitized, view_box, width_px, height_px = sanitize_bytes(source.read_bytes())
            destination.write_bytes(sanitized)
        else:
            try:
                with Image.open(source) as image:
                    image.load()
                    if image.format != expected_format:
                        raise AssetError("asset media_type does not match decoded image", path=item["path"], code="invalid_asset")
                    width_px, height_px = image.size
            except AssetError:
                raise
            except Exception as exc:
                raise AssetError("asset image cannot be decoded", path=item["path"], code="invalid_asset") from exc
            shutil.copyfile(source, destination)
        staged_hash = sha256_file(destination)
        record = {
            "id": item["asset_id"],
            "type": kind,
            "path": str(destination.resolve()),
            "sha256": staged_hash,
            "source_sha256": source_hash,
            "size_bytes": destination.stat().st_size,
            "width_px": width_px,
            "height_px": height_px,
            "media_type": item["media_type"],
            "contains_text": item["contains_text"],
        }
        if view_box is not None:
            record["view_box"] = view_box
        staged.append(record)
    return staged
