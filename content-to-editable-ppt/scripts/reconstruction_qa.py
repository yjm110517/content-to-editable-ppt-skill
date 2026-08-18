from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from PIL import Image, ImageChops, ImageFilter, ImageStat

from canonical_artifact import canonical_sha256
from reconstruction_authority import SCHEMA_DIR, file_sha256
from schema_utils import ContractError, error, load_json, validate_schema


NS = {"a":"http://schemas.openxmlformats.org/drawingml/2006/main","p":"http://schemas.openxmlformats.org/presentationml/2006/main","r":"http://schemas.openxmlformats.org/officeDocument/2006/relationships","pr":"http://schemas.openxmlformats.org/package/2006/relationships"}


def inspect_reconstruction_page(*, pptx_path: Path, spec_path: Path, build_report_path: Path) -> dict[str, Any]:
    spec = load_json(spec_path); report = load_json(build_report_path)
    validate_schema("visual_reconstruction_spec", spec, SCHEMA_DIR); validate_schema("reconstruction_build_report", report, SCHEMA_DIR)
    failures: list[dict[str, str]] = []
    if report["output_pptx_sha256"] != file_sha256(pptx_path): failures.append(error("$.output_pptx_sha256", "built PPTX hash mismatch", "authority_hash_mismatch"))
    if report["spec_sha256"] != file_sha256(spec_path): failures.append(error("$.spec_sha256", "build does not bind exact spec bytes", "authority_hash_mismatch"))
    if report["expected_element_count"] != len(spec["elements"]) or report["built_element_count"] != len(spec["elements"]): failures.append(error("$.built_element_count", "element reconciliation failed", "missing_element"))
    if report["full_slide_raster_substitution"]: failures.append(error("$.full_slide_raster_substitution", "full-slide raster substitution is forbidden", "full_slide_raster_substitution"))
    try:
        with zipfile.ZipFile(pptx_path) as archive:
            names = archive.namelist(); slides = [name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
            if slides != ["ppt/slides/slide1.xml"]: failures.append(error("$.pptx.slides", "page build must contain exactly one slide", "invalid_slide_count"))
            xml = archive.read("ppt/slides/slide1.xml"); root = ET.fromstring(xml)
            object_names = {item.attrib.get("name") for item in root.findall(".//p:cNvPr", NS)}
            text = "".join(node.text or "" for node in root.findall(".//a:t", NS))
            rel_path = "ppt/slides/_rels/slide1.xml.rels"; rel_root = ET.fromstring(archive.read(rel_path)) if rel_path in names else None
            if rel_root is not None:
                for relation in rel_root.findall("pr:Relationship", NS):
                    if relation.attrib.get("TargetMode") == "External" or relation.attrib.get("Target", "").startswith(("http:", "https:", "file:")): failures.append(error("$.pptx.relationships", "external relationship is forbidden", "unsafe_relationship"))
            for index, item in enumerate(spec["elements"]):
                if f"ivt:{item['element_id']}" not in object_names: failures.append(error(f"$.elements[{index}]", "expected PowerPoint object is missing", "missing_element"))
                if item["reconstruction_class"] == "native_text" and item["implementation"]["text"] not in text: failures.append(error(f"$.elements[{index}].implementation.text", "formal text is not present as native PowerPoint text", "content_drift"))
            chart_expected = any(item["reconstruction_class"] == "native_chart" for item in spec["elements"])
            chart_present = any(name.startswith("ppt/charts/chart") for name in names)
            if chart_expected != chart_present: failures.append(error("$.pptx.charts", "native chart relationship mismatch", "chart_drift"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        failures.append(error("$.pptx", f"PPTX inspection failed: {exc}", "invalid_pptx"))
    return {"schema_version":"1.0","artifact_type":"reconstruction_structural_qa","deck_id":spec["deck_id"],"slide_id":spec["slide_id"],"spec_sha256":canonical_sha256(spec),"pptx_sha256":file_sha256(pptx_path),"content_drift":sum(item["code"]=="content_drift" for item in failures),"chart_drift":sum(item["code"]=="chart_drift" for item in failures),"asset_drift":sum(item["code"]=="authority_hash_mismatch" for item in failures),"missing_elements":sum(item["code"]=="missing_element" for item in failures),"unsafe_relationships":sum(item["code"]=="unsafe_relationship" for item in failures),"status":"pass" if not failures else "fail","blocking_issues":failures}


def _image(path: Path, size: tuple[int, int] | None = None) -> Image.Image:
    with Image.open(path) as source:
        image = source.convert("RGB")
        return image.resize(size, Image.Resampling.LANCZOS) if size and image.size != size else image.copy()


def _milli_mean(diff: Image.Image) -> int:
    return round(sum(ImageStat.Stat(diff).mean) / 3 / 255 * 1000)


def compare_visual_fidelity(*, deck_id: str, slide_id: str, approved_preview: Path, candidate_render: Path) -> dict[str, Any]:
    approved = _image(approved_preview); candidate = _image(candidate_render, approved.size)
    rgb = _milli_mean(ImageChops.difference(approved, candidate))
    approved_edges = approved.convert("L").filter(ImageFilter.FIND_EDGES); candidate_edges = candidate.convert("L").filter(ImageFilter.FIND_EDGES)
    edge = round(ImageStat.Stat(ImageChops.difference(approved_edges, candidate_edges)).mean[0] / 255 * 1000)
    regions = []
    width, height = approved.size
    for row in range(3):
        for column in range(3):
            box = (column * width // 3, row * height // 3, (column + 1) * width // 3, (row + 1) * height // 3)
            regions.append(_milli_mean(ImageChops.difference(approved.crop(box), candidate.crop(box))))
    region = max(regions)
    if rgb <= 350 and edge <= 600 and region <= 550: classification = "pass"
    elif rgb <= 500 and region <= 700: classification = "reviewer_candidate"
    elif rgb <= 700 and region <= 850: classification = "targeted_patch_candidate"
    else: classification = "blocking_structural_drift"
    result = {"schema_version":"1.0","artifact_type":"visual_fidelity_report","deck_id":deck_id,"slide_id":slide_id,"approved_preview_sha256":file_sha256(approved_preview),"candidate_render_sha256":file_sha256(candidate_render),"classification":classification,"metrics":{"rgb_mean_absolute_error_milli":rgb,"edge_difference_milli":edge,"region_difference_milli":region},"reviewer_required":classification=="reviewer_candidate","blocking_issues":[] if classification != "blocking_structural_drift" else ["deterministic anomaly detector found extreme structural drift"]}
    validate_schema("visual_fidelity_report", result, SCHEMA_DIR); return result
