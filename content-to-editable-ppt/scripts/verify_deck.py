from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from deck_build_request import DIMENSIONS, load_request, normalized_text, sha256_file
from schema_utils import ContractError, error, load_json


COMPONENT = "verify_deck"
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
OBJECT_TAGS = {f"{{{NS['p']}}}sp", f"{{{NS['p']}}}pic", f"{{{NS['p']}}}graphicFrame", f"{{{NS['p']}}}cxnSp", f"{{{NS['p']}}}grpSp"}
EMU_PER_INCH = 914400


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Verify a direct multi-page editable PowerPoint deck.")
    result.add_argument("--request", type=Path, required=True)
    result.add_argument("--pptx", type=Path, required=True)
    result.add_argument("--build-report", type=Path, required=True)
    result.add_argument("--staged-assets", type=Path, required=True)
    result.add_argument("--render-report", type=Path, required=True)
    result.add_argument("--roundtrip-report", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


def _slide_names(archive: zipfile.ZipFile) -> list[str]:
    names = [name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)]
    return sorted(names, key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)))


def _objects(root: ET.Element) -> list[ET.Element]:
    tree = root.find(f".//{{{NS['p']}}}spTree")
    return [] if tree is None else [item for item in list(tree) if item.tag in OBJECT_TAGS]


def _name(element: ET.Element) -> str:
    found = element.find(f".//{{{NS['p']}}}cNvPr")
    return "" if found is None else found.get("name", "")


def _bounds(element: ET.Element) -> dict[str, float] | None:
    transform = element.find(f".//{{{NS['a']}}}xfrm")
    if transform is None:
        transform = element.find(f".//{{{NS['p']}}}xfrm")
    if transform is None:
        return None
    offset = transform.find(f"{{{NS['a']}}}off")
    extent = transform.find(f"{{{NS['a']}}}ext")
    if offset is None or extent is None:
        return None
    try:
        return {"x": int(offset.get("x", "0")) / EMU_PER_INCH, "y": int(offset.get("y", "0")) / EMU_PER_INCH, "w": int(extent.get("cx", "0")) / EMU_PER_INCH, "h": int(extent.get("cy", "0")) / EMU_PER_INCH}
    except ValueError:
        return None


def _text(element: ET.Element) -> str:
    paragraphs: list[str] = []
    for paragraph in element.findall(f".//{{{NS['a']}}}p"):
        parts: list[str] = []
        for child in list(paragraph):
            if child.tag == f"{{{NS['a']}}}br":
                parts.append("\n")
            else:
                value = child.find(f".//{{{NS['a']}}}t")
                if value is not None:
                    parts.append(value.text or "")
        paragraphs.append("".join(parts))
    return unicodedata.normalize("NFC", "\n".join(paragraphs).replace("\r\n", "\n").replace("\r", "\n"))


def _kind(element: ET.Element) -> str:
    if element.tag == f"{{{NS['p']}}}pic": return "image"
    if element.tag == f"{{{NS['p']}}}cxnSp": return "line"
    if element.tag == f"{{{NS['p']}}}graphicFrame": return "chart" if element.find(f".//{{{NS['c']}}}chart") is not None else "graphic"
    if element.tag == f"{{{NS['p']}}}sp": return "text" if element.find(f".//{{{NS['a']}}}t") is not None else "shape"
    return "group"


def _relationship_source(name: str) -> str:
    if name == "_rels/.rels": return ""
    prefix, filename = name.rsplit("/_rels/", 1)
    return f"{prefix}/{filename.removesuffix('.rels')}"


def _resolve_target(source: str, target: str) -> str | None:
    # OPC permits package-root-relative targets such as /ppt/charts/chart1.xml.
    # They are not filesystem-absolute paths and must be checked against the ZIP
    # member set after stripping the package-root slash.
    combined = posixpath.normpath(target.lstrip("/")) if target.startswith("/") else posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
    return None if combined.startswith("..") or combined.startswith("/") else combined


def _relationships(archive: zipfile.ZipFile, rel_name: str) -> dict[str, str]:
    source = _relationship_source(rel_name)
    result: dict[str, str] = {}
    root = ET.fromstring(archive.read(rel_name))
    for relation in root:
        target = relation.get("Target", "")
        mode = relation.get("TargetMode", "Internal")
        if mode == "External" or target.startswith(("http://", "https://", "ftp://", "file:", "mailto:", "\\")) or re.match(r"^[A-Za-z]:[/\\]", target):
            result[relation.get("Id", "")] = "!external!"
        else:
            result[relation.get("Id", "")] = _resolve_target(source, target) or "!escape!"
    return result


def _intersects(left: dict[str, float], right: dict[str, float], tolerance: float = 0.5 / 72) -> bool:
    return min(left["x"] + left["w"], right["x"] + right["w"]) - max(left["x"], right["x"]) > tolerance and min(left["y"] + left["h"], right["y"] + right["h"]) - max(left["y"], right["y"]) > tolerance


def verify(*, request_path: Path, pptx: Path, build_report_path: Path, staged_assets_path: Path, render_report_path: Path, roundtrip_report_path: Path) -> dict[str, Any]:
    request = load_request(request_path)
    build = load_json(build_report_path); render = load_json(render_report_path); roundtrip = load_json(roundtrip_report_path)
    try:
        staged = json.loads(staged_assets_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError([error("$.staged_assets", "staged asset index is not valid JSON", "invalid_staged_assets")]) from exc
    if not isinstance(staged, list) or not all(isinstance(item, dict) for item in staged):
        raise ContractError([error("$.staged_assets", "staged asset index must be an array of objects", "invalid_staged_assets")])
    issues: list[dict[str, str]] = []
    pptx_hash = sha256_file(pptx)
    if build.get("request_sha256") != sha256_file(request_path) or build.get("pptx_sha256") != pptx_hash:
        issues.append(error("$.build_report", "build report does not bind request and PPTX", "authority_mismatch"))
    if render.get("status") != "pass" or render.get("ppt_sha256") != pptx_hash:
        issues.append(error("$.render_report", "render report does not bind PPTX", "render_mismatch"))
    dimensions = DIMENSIONS[request["output_ratio"]]
    if render.get("width_px") != dimensions["width_px"] or render.get("height_px") != dimensions["height_px"] or render.get("rendered_page_count") != len(request["slides"]):
        issues.append(error("$.render_report", "render dimensions or slide count mismatch", "render_mismatch"))
    if roundtrip.get("status") != "pass" or roundtrip.get("original_candidate_sha256") != pptx_hash:
        issues.append(error("$.roundtrip_report", "PowerPoint roundtrip did not pass for this PPTX", "roundtrip_failed"))
    staged_by_id = {item["id"]: item for item in staged}
    actual_pages: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(pptx) as archive:
            names = set(archive.namelist())
            slides = _slide_names(archive)
            if len(slides) != len(request["slides"]):
                issues.append(error("$.slides", "PPTX slide count mismatch", "slide_count"))
            for rel_name in sorted(name for name in names if name.endswith(".rels")):
                for relation_id, target in _relationships(archive, rel_name).items():
                    if target in {"!external!", "!escape!"} or target not in names:
                        issues.append(error(f"$.relationships.{rel_name}.{relation_id}", f"unsafe or missing relationship target: {target}", "unsafe_relationship"))
            active = [name for name in names if name.lower().endswith("vbaproject.bin") or "/activex/" in name.lower() or "/ole" in name.lower() or "externallink" in name.lower()]
            if active:
                issues.append(error("$.package", f"active content is forbidden: {active}", "active_content"))
            if "[Content_Types].xml" in names:
                lowered = archive.read("[Content_Types].xml").lower()
                if any(token in lowered for token in (b"macroenabled", b"vba", b"activex", b"oleobject", b"externallink")):
                    issues.append(error("$.[Content_Types]", "active content type is forbidden", "active_content"))
            ordered = sorted(request["slides"], key=lambda item: item["order"])
            for index, slide_name in enumerate(slides):
                if index >= len(ordered): break
                expected_page = ordered[index]; root = ET.fromstring(archive.read(slide_name)); objects = _objects(root)
                named: dict[str, ET.Element] = {}
                duplicates: list[str] = []
                for item in objects:
                    name = _name(item)
                    if name in named: duplicates.append(name)
                    named[name] = item
                if duplicates:
                    issues.append(error(f"$.slides[{index}]", f"duplicate object names: {duplicates}", "duplicate_object"))
                expected_names = [f"ivt:{item['id']}" for item in expected_page["elements"]]
                if set(named) != set(expected_names):
                    issues.append(error(f"$.slides[{index}]", f"object identity mismatch; expected={expected_names}, actual={sorted(named)}", "element_identity"))
                page_objects: list[dict[str, Any]] = []
                text_bounds: list[tuple[str, dict[str, float]]] = []; image_bounds: list[tuple[str, dict[str, float]]] = []
                rel_name = f"ppt/slides/_rels/slide{index + 1}.xml.rels"; rels = _relationships(archive, rel_name) if rel_name in names else {}
                for expected in expected_page["elements"]:
                    object_name = f"ivt:{expected['id']}"; actual = named.get(object_name)
                    if actual is None: continue
                    actual_kind = _kind(actual)
                    if actual_kind != expected["type"] and not (expected["type"] == "line" and actual_kind == "shape"):
                        issues.append(error(f"$.slides[{index}].{expected['id']}", f"native type mismatch: {actual_kind}", "native_type"))
                    bounds = _bounds(actual)
                    if bounds is None:
                        issues.append(error(f"$.slides[{index}].{expected['id']}", "object has no bounds", "missing_bounds")); continue
                    for field in ("x", "y", "w", "h"):
                        if abs(bounds[field] - float(expected[field])) > 0.5 / 72:
                            issues.append(error(f"$.slides[{index}].{expected['id']}.{field}", "object bounds drift", "geometry_drift"))
                    if expected["type"] == "text":
                        if _text(actual) != normalized_text(expected):
                            issues.append(error(f"$.slides[{index}].{expected['id']}", "native text identity mismatch", "text_identity"))
                        text_bounds.append((expected["id"], bounds))
                    elif expected["type"] == "image":
                        image_bounds.append((expected["id"], bounds))
                        blip = actual.find(f".//{{{NS['a']}}}blip"); relation_id = None if blip is None else blip.get(f"{{{NS['r']}}}embed")
                        target = rels.get(relation_id or "", "")
                        staged_asset = staged_by_id.get(expected["asset_id"])
                        if not target or target not in names or staged_asset is None or hashlib.sha256(archive.read(target)).hexdigest() != staged_asset["sha256"]:
                            issues.append(error(f"$.slides[{index}].{expected['id']}", "embedded media does not bind staged asset", "media_mismatch"))
                    page_objects.append({"element_id": expected["id"], "type": actual_kind, "bounds": bounds})
                for image_id, image_box in image_bounds:
                    for text_id, text_box in text_bounds:
                        if _intersects(image_box, text_box):
                            issues.append(error(f"$.slides[{index}]", f"actual image {image_id} overlaps text {text_id}", "image_text_overlap"))
                if len(objects) == 1 and _kind(objects[0]) == "image":
                    bounds = _bounds(objects[0])
                    if bounds and bounds["w"] >= dimensions["width_in"] * 0.995 and bounds["h"] >= dimensions["height_in"] * 0.995:
                        issues.append(error(f"$.slides[{index}]", "full-slide raster substitution", "full_slide_raster_substitution"))
                actual_pages.append({"slide_id": expected_page["slide_id"], "order": expected_page["order"], "objects": page_objects})
    except (zipfile.BadZipFile, ET.ParseError, KeyError, ValueError) as exc:
        issues.append(error("$.pptx", f"invalid PPTX package: {exc}", "invalid_pptx"))
    return {"schema_version": "1.0", "artifact_type": "direct_deck_quality_report", "deck_id": request["deck_id"], "pptx_sha256": pptx_hash, "slide_count": len(actual_pages), "pages": actual_pages, "issues": issues, "status": "pass" if not issues else "fail"}


def main() -> int:
    args = parser().parse_args()
    try:
        if args.output.exists():
            raise ContractError([error("$.output", "quality report already exists", "output_collision")])
        report = verify(request_path=args.request, pptx=args.pptx, build_report_path=args.build_report, staged_assets_path=args.staged_assets, render_report_path=args.render_report, roundtrip_report_path=args.roundtrip_report)
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"status": "ok" if report["status"] == "pass" else "error", "component": COMPONENT, "outputs": {"report": str(args.output.resolve())}, "error": None if report["status"] == "pass" else {"exit_code": 8, "category": "structural_qa", "issues": report["issues"]}}, ensure_ascii=False))
        return 0 if report["status"] == "pass" else 8
    except Exception as exc:
        issues = exc.errors if isinstance(exc, ContractError) else [error("$", str(exc), "verify_deck_internal_error")]
        print(json.dumps({"status": "error", "component": COMPONENT, "outputs": {}, "error": {"exit_code": 8 if isinstance(exc, ContractError) else 70, "category": "structural_qa", "issues": issues}}, ensure_ascii=False))
        return 8 if isinstance(exc, ContractError) else 70


if __name__ == "__main__":
    raise SystemExit(main())
