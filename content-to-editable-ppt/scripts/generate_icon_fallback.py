from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from defusedxml import ElementTree as SafeET

from canonical_artifact import canonical_sha256
from resolve_icon_asset import (
    EXPECTED_VERSION,
    SCHEMA_DIR,
    find_visual,
    json_bytes,
    sha256_bytes,
    sha256_file,
    validate_direction,
    validate_p2,
    write_once,
)
from schema_utils import ContractError, error, load_json, validate_schema


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def qname(name: str) -> str:
    return f"{{{SVG_NS}}}{name}"


def svg_bytes(root: ET.Element) -> bytes:
    for element in root.iter():
        ordered = sorted(element.attrib.items())
        element.attrib.clear()
        element.attrib.update(ordered)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True, short_empty_elements=True) + b"\n"


def root_svg() -> ET.Element:
    return ET.Element(qname("svg"), {"width": "24", "height": "24", "viewBox": "0 0 24 24", "fill": "none", "stroke": "currentColor", "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round"})


def safe_tabler_source(vendor_root: Path, icon_name: str) -> Path:
    source = (vendor_root.resolve() / "icons" / "outline" / f"{icon_name}.svg").resolve()
    try:
        source.relative_to(vendor_root.resolve())
    except ValueError as exc:
        raise ContractError([error("$.components", "component path escapes pinned vendor", "unsafe_path")]) from exc
    if not source.is_file():
        raise ContractError([error("$.components", f"unknown Tabler icon: {icon_name}", "unknown_icon")])
    return source


def compose(args: argparse.Namespace) -> dict[str, Any]:
    if len(args.icon_name) != 2:
        raise ContractError([error("$.components", "composition requires exactly two Tabler icons", "composition_limit")])
    manifest, manifest_sha = validate_p2(args.p2_manifest.resolve(), args.wireframe_root.resolve())
    find_visual(manifest, args.visual_ref)
    validate_direction(args.visual_direction.resolve(), manifest, manifest_sha)
    sources = [safe_tabler_source(args.vendor_root, name) for name in args.icon_name]
    root = root_svg()
    transforms = ("translate(1 4) scale(.65)", "translate(8 4) scale(.65)")
    for source, transform in zip(sources, transforms):
        parsed = SafeET.fromstring(source.read_bytes())
        group = ET.SubElement(root, qname("g"), {"transform": transform})
        for child in list(parsed):
            group.append(child)
    source_bytes = svg_bytes(root)
    record = {
        "schema_version": "1.0", "artifact_type": "icon_resolution_record", "visual_ref": args.visual_ref,
        "p2_manifest_sha256": manifest_sha, "resolution_method": "tabler_composition", "library": "tabler-icons",
        "library_version": EXPECTED_VERSION,
        "components": [{"icon_name": name, "source_sha256": sha256_file(path)} for name, path in zip(args.icon_name, sources)],
        "source_sha256": sha256_bytes(source_bytes), "selection_method": "bounded_fallback", "created_at_utc": args.created_at_utc,
    }
    validate_schema("icon_resolution", record, SCHEMA_DIR)
    write_once(args.output_source.resolve(), source_bytes)
    write_once(args.output_record.resolve(), json_bytes(record))
    return {"source_svg_sha256": record["source_sha256"], "resolution_record_sha256": canonical_sha256(record)}


def primitive_count(items: list[dict[str, Any]]) -> int:
    return sum(primitive_count(item["children"]) if item["type"] == "group" else 1 for item in items)


def group_depth(items: list[dict[str, Any]], depth: int = 0) -> int:
    return max([depth] + [group_depth(item["children"], depth + 1) for item in items if item["type"] == "group"])


def validate_geometry(item: dict[str, Any]) -> None:
    if item["type"] == "rect" and (item["x"] + item["width"] > 24 or item["y"] + item["height"] > 24):
        raise ContractError([error("$.primitives", "rectangle exceeds 24x24 bounds", "drawing_out_of_bounds")])
    if item["type"] in {"circle", "ellipse"}:
        rx = item["r"] if item["type"] == "circle" else item["rx"]
        ry = item["r"] if item["type"] == "circle" else item["ry"]
        if item["cx"] - rx < 0 or item["cx"] + rx > 24 or item["cy"] - ry < 0 or item["cy"] + ry > 24:
            raise ContractError([error("$.primitives", "ellipse exceeds 24x24 bounds", "drawing_out_of_bounds")])
    if item["type"] == "group":
        for child in item["children"]:
            validate_geometry(child)


def render_primitive(parent: ET.Element, item: dict[str, Any]) -> None:
    kind = item["type"]
    if kind == "group":
        group = ET.SubElement(parent, qname("g"))
        for child in item["children"]:
            render_primitive(group, child)
        return
    if kind in {"line", "arrow"}:
        ET.SubElement(parent, qname("line"), {key: str(item[key]) for key in ("x1", "y1", "x2", "y2")})
        if kind == "arrow":
            angle = math.atan2(item["y2"] - item["y1"], item["x2"] - item["x1"])
            points = []
            for delta in (math.pi * .75, -math.pi * .75):
                points.append(f"{item['x2'] + 3 * math.cos(angle + delta):.3f},{item['y2'] + 3 * math.sin(angle + delta):.3f}")
            ET.SubElement(parent, qname("polyline"), {"points": " ".join([points[0], f"{item['x2']},{item['y2']}", points[1]])})
    elif kind == "rect":
        ET.SubElement(parent, qname("rect"), {key: str(item[key]) for key in ("x", "y", "width", "height") if key in item} | ({"rx": str(item["rx"])} if "rx" in item else {}))
    elif kind == "circle":
        ET.SubElement(parent, qname("circle"), {key: str(item[key]) for key in ("cx", "cy", "r")})
    elif kind == "ellipse":
        ET.SubElement(parent, qname("ellipse"), {key: str(item[key]) for key in ("cx", "cy", "rx", "ry")})
    elif kind == "polyline":
        ET.SubElement(parent, qname("polyline"), {"points": " ".join(f"{point['x']},{point['y']}" for point in item["points"])})


def draw(args: argparse.Namespace) -> dict[str, Any]:
    manifest, manifest_sha = validate_p2(args.p2_manifest.resolve(), args.wireframe_root.resolve())
    find_visual(manifest, args.visual_ref)
    validate_direction(args.visual_direction.resolve(), manifest, manifest_sha)
    drawing = load_json(args.drawing.resolve())
    validate_schema("simple_icon_drawing", drawing, SCHEMA_DIR)
    if drawing["visual_ref"] != args.visual_ref:
        raise ContractError([error("$.drawing.visual_ref", "drawing does not bind requested placeholder", "authority_hash_mismatch")])
    if primitive_count(drawing["primitives"]) > 12 or group_depth(drawing["primitives"]) > 3:
        raise ContractError([error("$.drawing.primitives", "drawing exceeds primitive or group-depth limit", "drawing_limit")])
    for item in drawing["primitives"]:
        validate_geometry(item)
    root = root_svg()
    for item in drawing["primitives"]:
        render_primitive(root, item)
    source_bytes = svg_bytes(root)
    record = {
        "schema_version": "1.0", "artifact_type": "icon_resolution_record", "visual_ref": args.visual_ref,
        "p2_manifest_sha256": manifest_sha, "resolution_method": "programmatic_svg",
        "source_sha256": sha256_bytes(source_bytes), "selection_method": "bounded_fallback",
        "drawing_spec_sha256": canonical_sha256(drawing), "created_at_utc": args.created_at_utc,
    }
    validate_schema("icon_resolution", record, SCHEMA_DIR)
    write_once(args.output_source.resolve(), source_bytes)
    write_once(args.output_record.resolve(), json_bytes(record))
    return {"source_svg_sha256": record["source_sha256"], "resolution_record_sha256": canonical_sha256(record)}


def handoff(args: argparse.Namespace) -> dict[str, Any]:
    manifest, manifest_sha = validate_p2(args.p2_manifest.resolve(), args.wireframe_root.resolve())
    find_visual(manifest, args.visual_ref)
    validate_direction(args.visual_direction.resolve(), manifest, manifest_sha)
    record = {
        "schema_version": "1.0", "artifact_type": "raster_icon_handoff", "visual_ref": args.visual_ref,
        "p2_manifest_sha256": manifest_sha, "reason": args.reason, "status": "raster_handoff_required",
        "created_at_utc": args.created_at_utc,
    }
    validate_schema("raster_icon_handoff", record, SCHEMA_DIR)
    write_once(args.output.resolve(), json_bytes(record))
    return {"handoff_record": str(args.output.resolve()), "status": record["status"]}


def common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--p2-manifest", type=Path, required=True)
    parser.add_argument("--wireframe-root", type=Path, required=True)
    parser.add_argument("--visual-direction", type=Path, required=True)
    parser.add_argument("--visual-ref", required=True)
    parser.add_argument("--created-at-utc", required=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Create bounded P3.1 icon fallback artifacts")
    sub = result.add_subparsers(dest="action", required=True)
    composition = sub.add_parser("compose")
    common(composition)
    composition.add_argument("--vendor-root", type=Path, required=True)
    composition.add_argument("--icon-name", action="append", required=True)
    composition.add_argument("--output-source", type=Path, required=True)
    composition.add_argument("--output-record", type=Path, required=True)
    drawing = sub.add_parser("draw")
    common(drawing)
    drawing.add_argument("--drawing", type=Path, required=True)
    drawing.add_argument("--output-source", type=Path, required=True)
    drawing.add_argument("--output-record", type=Path, required=True)
    raster = sub.add_parser("raster-handoff")
    common(raster)
    raster.add_argument("--reason", choices=["no_suitable_svg", "complex_visual_required", "accessibility_requirement"], required=True)
    raster.add_argument("--output", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        outputs = {"compose": compose, "draw": draw, "raster-handoff": handoff}[args.action](args)
        print(json.dumps({"status": "ok", "outputs": outputs}, ensure_ascii=False))
        return 0
    except (ContractError, OSError, ValueError, ET.ParseError) as exc:
        errors = exc.errors if isinstance(exc, ContractError) else [{"path": "$", "code": "fallback_error", "message": str(exc)}]
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
