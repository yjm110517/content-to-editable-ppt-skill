from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from decimal import Decimal, ROUND_HALF_EVEN
from html import escape
from pathlib import Path
from typing import Any

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
VIEWBOX = {"16:9": (1600, 900), "4:3": (1200, 900)}
FORBIDDEN = re.compile(r"(?i)(?:file:|data:|javascript:|[A-Za-z]:\\|\\\\)")
ROLE_STYLE = {
    "container": ("#F8FAFC", "#94A3B8", "6 4"),
    "title": ("#E2E8F0", "#475569", ""),
    "content": ("#F1F5F9", "#64748B", ""),
    "image": ("#E5E7EB", "#6B7280", "8 5"),
    "chart": ("#E5E7EB", "#6B7280", "8 5"),
    "diagram": ("#E5E7EB", "#6B7280", "8 5"),
    "footer": ("#F8FAFC", "#94A3B8", ""),
    "decoration": ("none", "#CBD5E1", "4 4"),
}


def canonical_number(value: Decimal | int) -> str:
    decimal = value if isinstance(value, Decimal) else Decimal(value)
    rounded = decimal.quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)
    if rounded == 0:
        return "0"
    result = format(rounded, "f").rstrip("0").rstrip(".")
    return "0" if result == "-0" else result


def project(value: int, dimension: int) -> str:
    return canonical_number(Decimal(value) * Decimal(dimension) / Decimal(10000))


def display_width(value: str) -> int:
    return sum(0 if unicodedata.combining(char) else 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1 for char in value)


def truncate_cells(value: str, capacity: int) -> tuple[str, str]:
    if display_width(value) <= capacity:
        return value, "full"
    budget = max(1, capacity - 1)
    result = []
    used = 0
    for char in value:
        width = display_width(char)
        if used + width > budget:
            break
        result.append(char)
        used += width
    return "".join(result).rstrip() + "…", "truncated"


def wrap_cells(value: str, cells_per_line: int) -> list[str]:
    lines: list[str] = []
    for hard_line in value.split("\n"):
        current: list[str] = []
        width = 0
        for char in hard_line:
            char_width = display_width(char)
            if current and width + char_width > cells_per_line:
                lines.append("".join(current))
                current, width = [], 0
            current.append(char)
            width += char_width
        lines.append("".join(current))
    return lines or [""]


def content_map(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {document["title"]["content_ref"]: document["title"], **{item["content_ref"]: item for item in document["content_blocks"]}}


def _attrs(values: dict[str, Any]) -> str:
    return " ".join(f'{name}="{escape(str(value), quote=True)}"' for name, value in values.items() if value is not None and value != "")


def _region_svg(region: dict[str, Any], *, width: int, height: int) -> str:
    fill, stroke, dash = ROLE_STYLE[region["role"]]
    attrs = {
        "id": region["region_id"], "data-role": region["role"],
        "data-semantic-source-refs": ",".join(region["semantic_source_refs"]),
        "x": project(region["bbox"]["x"], width), "y": project(region["bbox"]["y"], height),
        "width": project(region["bbox"]["w"], width), "height": project(region["bbox"]["h"], height),
        "rx": "5", "fill": fill, "stroke": stroke, "stroke-width": "1.5", "stroke-dasharray": dash,
    }
    return f"  <rect {_attrs(attrs)}/>"


def preview_text(
    region: dict[str, Any], authority_item: dict[str, Any], index: int, count: int
) -> tuple[str, str, list[str], int]:
    """Return the one canonical preview calculation used by render and audit."""
    del index  # Position affects SVG coordinates, not the displayed preview text.
    box = region["bbox"]
    part_height = max(1, box["h"] // max(1, count))
    cells_per_line = max(4, box["w"] // (220 if region["role"] == "title" else 170))
    max_lines = max(1, part_height // (700 if region["role"] == "title" else 520))
    capacity = max(4, cells_per_line * max_lines)
    preview, mode = truncate_cells(authority_item["text"], capacity)
    ordered_lines = wrap_cells(preview, cells_per_line)[:max_lines]
    return preview, mode, ordered_lines, part_height


def _text_svg(*, region: dict[str, Any], item: dict[str, Any], index: int, count: int, width: int, height: int) -> tuple[str, dict[str, Any] | None]:
    box = region["bbox"]
    font_size = 28 if region["role"] == "title" else 14 if region["role"] == "footer" else 18
    preview, mode, lines, part_height = preview_text(region, item, index, count)
    x = project(box["x"] + 180, width)
    base_y = box["y"] + index * part_height + 260
    line_height = font_size * Decimal("1.25")
    tspans = []
    for line_index, line in enumerate(lines):
        y = Decimal(project(base_y, height)) + Decimal(line_index) * line_height
        tspans.append(f'      <tspan x="{x}" y="{canonical_number(y)}">{escape(line)}</tspan>')
    authority_hash = canonical_sha256(item)
    group_attrs = {
        "data-content-ref": item["content_ref"], "data-authority-sha256": authority_hash,
        "data-preview-display": mode, "data-authority-length": len(item["text"]),
    }
    warning = None if mode == "full" else {"code": "preview_text_truncated", "content_ref": item["content_ref"], "authority_sha256": authority_hash}
    group = [f"    <g {_attrs(group_attrs)}>", f'      <text font-family="Arial, Microsoft YaHei, sans-serif" font-size="{font_size}" fill="#111827">', *tspans, "      </text>", "    </g>"]
    return "\n".join(group), warning


def render_document(spec: dict[str, Any], slide_content: dict[str, Any]) -> tuple[bytes, list[dict[str, Any]]]:
    validate_schema("wireframe_spec", spec, SCHEMA_DIR)
    validate_schema("approved_slide_content", slide_content, SCHEMA_DIR)
    if spec["deck_id"] != slide_content["deck_id"] or spec["slide_id"] != slide_content["slide_id"]:
        raise ContractError([error("$", "Wireframe Spec and Approved Slide Content identity mismatch", "authority_identity_mismatch")])
    if spec["authority"]["approved_slide_content_sha256"] != canonical_sha256(slide_content):
        raise ContractError([error("$.authority.approved_slide_content_sha256", "Spec does not bind Slide Content", "authority_hash_mismatch")])
    width, height = VIEWBOX[spec["output_ratio"]]
    regions = sorted(spec["regions"], key=lambda item: (item["z_index"], item["region_id"]))
    texts = content_map(slide_content)
    warnings: list[dict[str, Any]] = []
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" data-deck-id="{escape(spec["deck_id"], quote=True)}" data-slide-id="{escape(spec["slide_id"], quote=True)}" data-wireframe-spec-sha256="{canonical_sha256(spec)}">',
        f'  <rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>',
    ]
    for region in regions:
        parts.append(_region_svg(region, width=width, height=height))
        for index, ref in enumerate(region["content_refs"]):
            if ref not in texts:
                raise ContractError([error("$.regions.content_refs", f"unknown Content Ref: {ref}", "unknown_content_ref")])
            group, warning = _text_svg(region=region, item=texts[ref], index=index, count=len(region["content_refs"]), width=width, height=height)
            parts.append(group)
            if warning:
                warnings.append(warning)
        if region["role"] in {"image", "chart", "diagram"}:
            label_x = project(region["bbox"]["x"] + region["bbox"]["w"] // 2, width)
            label_y = project(region["bbox"]["y"] + region["bbox"]["h"] // 2, height)
            parts.append(f'  <text x="{label_x}" y="{label_y}" text-anchor="middle" data-wireframe-annotation="true" font-family="Arial, sans-serif" font-size="14" fill="#6B7280">[{region["role"].upper()}]</text>')
    by_id = {item["region_id"]: item for item in spec["regions"]}
    for relationship in sorted(spec["relationships"], key=lambda item: item["relationship_id"]):
        if relationship["kind"] == "overlay" or relationship["from_region_id"] not in by_id or relationship["to_region_id"] not in by_id:
            continue
        left, right = by_id[relationship["from_region_id"]]["bbox"], by_id[relationship["to_region_id"]]["bbox"]
        attrs = {
            "data-relationship-id": relationship["relationship_id"], "data-kind": relationship["kind"],
            "x1": project(left["x"] + left["w"] // 2, width), "y1": project(left["y"] + left["h"] // 2, height),
            "x2": project(right["x"] + right["w"] // 2, width), "y2": project(right["y"] + right["h"] // 2, height),
            "stroke": "#64748B", "stroke-width": "1.5",
        }
        parts.append(f"  <line {_attrs(attrs)}/>")
    parts.append("</svg>")
    output = ("\n".join(parts) + "\n").encode("utf-8")
    audit_svg(output, spec=spec, slide_content=slide_content)
    return output, warnings


def audit_svg(content: bytes, *, spec: dict[str, Any], slide_content: dict[str, Any]) -> dict[str, Any]:
    text = content.decode("utf-8")
    if FORBIDDEN.search(text) or re.search(r"(?i)<(?:script|foreignObject|image|style)\b|\son[a-z]+\s*=|\s(?:href|xlink:href)\s*=", text):
        raise ContractError([error("$", "Wireframe SVG contains active or external content", "unsafe_svg")])
    try:
        root = SafeET.fromstring(content)
    except (DefusedXmlException, SafeET.ParseError) as exc:
        raise ContractError([error("$", "Wireframe SVG is not safe well-formed XML", "unsafe_svg")]) from exc
    if root.tag.split("}")[-1] != "svg":
        raise ContractError([error("$", "Wireframe output root must be SVG", "invalid_svg")])
    groups = [item for item in root.iter() if "data-content-ref" in item.attrib]
    actual_refs = [item.attrib["data-content-ref"] for item in groups]
    expected = content_map(slide_content)
    if Counter(actual_refs) != Counter({key: 1 for key in expected}):
        raise ContractError([error("$", "SVG Content Ref groups do not exactly match Approved Content", "svg_content_mapping")])
    mapped_regions: dict[str, list[tuple[dict[str, Any], int, int]]] = {ref: [] for ref in expected}
    for region in spec["regions"]:
        refs = region["content_refs"]
        for index, ref in enumerate(refs):
            if ref in mapped_regions:
                mapped_regions[ref].append((region, index, len(refs)))
    for group in groups:
        ref = group.attrib["data-content-ref"]
        mappings = mapped_regions[ref]
        if len(mappings) != 1:
            raise ContractError([error("$", f"SVG Content Ref does not map to one Region: {ref}", "svg_content_mapping")])
        region, index, count = mappings[0]
        _, expected_mode, expected_lines, _ = preview_text(region, expected[ref], index, count)
        if group.attrib.get("data-authority-sha256") != canonical_sha256(expected[ref]):
            raise ContractError([error("$", f"SVG Authority Hash mismatch: {ref}", "svg_authority_hash")])
        if group.attrib.get("data-authority-length") != str(len(expected[ref]["text"])):
            raise ContractError([error("$", f"SVG Authority Length mismatch: {ref}", "svg_authority_length")])
        actual_mode = group.attrib.get("data-preview-display")
        actual_lines = ["".join(item.itertext()) for item in group.iter() if item.tag.split("}")[-1] == "tspan"]
        if actual_mode != expected_mode or actual_lines != expected_lines:
            raise ContractError([error("$", f"SVG Preview Text mismatch: {ref}", "svg_preview_text")])
    return {"status": "pass", "sha256": hashlib.sha256(content).hexdigest(), "content_refs": len(groups)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a deterministic low-fidelity P2 Wireframe SVG")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--slide-content", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        output_path = args.output.resolve()
        if output_path.exists():
            raise ContractError([error("--output", "Renderer refuses to overwrite existing SVG", "overwrite_forbidden")])
        content, warnings = render_document(load_json(args.spec.resolve()), load_json(args.slide_content.resolve()))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        report = {"status": "pass", "output_sha256": hashlib.sha256(content).hexdigest(), "warnings": warnings}
        if args.report:
            report_path = args.report.resolve()
            if report_path.exists():
                raise ContractError([error("--report", "Renderer refuses to overwrite existing report", "overwrite_forbidden")])
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except ContractError as exc:
        print(json.dumps({"status": "error", "errors": exc.errors}, ensure_ascii=False))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
