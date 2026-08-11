from __future__ import annotations

import copy
import hashlib
import json
import unicodedata
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


class TextIdentityError(ValueError):
    pass


def canonical_text(value: str) -> str:
    if not isinstance(value, str):
        raise TextIdentityError("text must be a string")
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
XML_NS = {"a": DRAWING_NS, "p": PRESENTATION_NS}


def canonical_json_sha256(document: Any) -> str:
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text_elements(layout: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in layout.get("elements", []) if item.get("type") == "text"]


def _element_text(element: dict[str, Any]) -> str:
    if "text" in element:
        return canonical_text(element["text"])
    pieces: list[str] = []
    for run in element.get("runs", []):
        pieces.append(canonical_text(run.get("text", "")))
        if run.get("break_line"):
            pieces.append("\n")
    return "".join(pieces)


def build_compatibility_map(
    layout: dict[str, Any],
    authority: dict[str, Any],
    explicit: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    explicit = explicit or {}
    elements = _text_elements(layout)
    element_by_id = {item["id"]: item for item in elements}
    mappings: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    used_elements: set[str] = set()

    for item in authority.get("text_items", []):
        content_ref = item["id"]
        wanted = canonical_text(item["text"])
        if content_ref in explicit:
            segments = copy.deepcopy(explicit[content_ref])
            for segment in segments:
                element = element_by_id.get(segment.get("element_id"))
                if element is None:
                    raise TextIdentityError(f"explicit mapping references unknown element: {segment.get('element_id')}")
            mappings.append({"content_ref": content_ref, "method": "explicit", "segments": segments})
            used_elements.update(segment["element_id"] for segment in segments)
            continue

        same_id = element_by_id.get(content_ref)
        if same_id is not None and _element_text(same_id) == wanted:
            candidates = [same_id]
            method = "same_id_and_text"
        else:
            candidates = [element for element in elements if _element_text(element) == wanted]
            method = "unique_text"

        candidates = [element for element in candidates if element["id"] not in used_elements]
        if len(candidates) == 1:
            element_id = candidates[0]["id"]
            mappings.append({
                "content_ref": content_ref,
                "method": method,
                "segments": [{"element_id": element_id, "segment_order": 0, "joiner": ""}],
            })
            used_elements.add(element_id)
        else:
            unresolved.append({
                "content_ref": content_ref,
                "reason": "missing" if not candidates else "ambiguous",
                "candidate_element_ids": sorted(element["id"] for element in candidates),
            })

    return {
        "schema_version": "1.0",
        "layout_sha256": canonical_json_sha256(layout),
        "authority_sha256": canonical_json_sha256(authority),
        "mappings": mappings,
        "unresolved": unresolved,
    }


def compatibility_view(layout: dict[str, Any], mapping: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    if strict and mapping.get("unresolved"):
        refs = ", ".join(item["content_ref"] for item in mapping["unresolved"])
        raise TextIdentityError(f"unresolved authority content: {refs}")
    result = copy.deepcopy(layout)
    result["schema_version"] = "1.4"
    elements = {item["id"]: item for item in _text_elements(result)}
    for item in mapping.get("mappings", []):
        for segment in item["segments"]:
            element = elements[segment["element_id"]]
            element["content_ref"] = item["content_ref"]
            element["segment_order"] = segment["segment_order"]
            element["joiner"] = segment["joiner"]
    return result


def compare_authority(authority: dict[str, Any], layout: dict[str, Any]) -> dict[str, Any]:
    expected = {item["id"]: canonical_text(item["text"]) for item in authority.get("text_items", [])}
    grouped: dict[str, list[dict[str, Any]]] = {}
    unknown: set[str] = set()
    for element in _text_elements(layout):
        content_ref = element.get("content_ref")
        if not content_ref:
            continue
        if content_ref not in expected:
            unknown.add(content_ref)
            continue
        grouped.setdefault(content_ref, []).append(element)

    missing: list[str] = []
    mismatched: list[dict[str, str]] = []
    duplicate_segment_orders: list[str] = []
    non_contiguous_segment_orders: list[str] = []
    for content_ref, wanted in expected.items():
        segments = sorted(grouped.get(content_ref, []), key=lambda item: item.get("segment_order", 0))
        if not segments:
            missing.append(content_ref)
            continue
        orders = [item.get("segment_order", 0) for item in segments]
        if len(set(orders)) != len(orders):
            duplicate_segment_orders.append(content_ref)
        if orders != list(range(len(orders))):
            non_contiguous_segment_orders.append(content_ref)
        actual = "".join(str(item.get("joiner", "")) + _element_text(item) for item in segments)
        actual = actual.replace("\v", "").replace("\u2028", "")
        if actual != wanted:
            mismatched.append({"content_ref": content_ref, "expected": wanted, "actual": actual})
    failed = missing or mismatched or unknown or duplicate_segment_orders or non_contiguous_segment_orders
    return {
        "status": "fail" if failed else "pass",
        "missing": sorted(missing),
        "mismatched": mismatched,
        "unknown": sorted(unknown),
        "duplicate_segment_orders": sorted(duplicate_segment_orders),
        "non_contiguous_segment_orders": sorted(non_contiguous_segment_orders),
    }


def _shape_text(shape: ET.Element) -> str:
    paragraphs: list[str] = []
    for paragraph in shape.findall("p:txBody/a:p", XML_NS):
        pieces: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{{{DRAWING_NS}}}t":
                pieces.append(node.text or "")
            elif node.tag == f"{{{DRAWING_NS}}}br":
                pieces.append("\n")
        paragraphs.append("".join(pieces))
    return "\n".join(paragraphs)


def extract_ppt_text_by_element(pptx: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        with zipfile.ZipFile(pptx) as archive:
            slides = sorted(
                (name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")),
                key=lambda name: int(Path(name).stem.removeprefix("slide")),
            )
            for slide in slides:
                root = ET.fromstring(archive.read(slide))
                for shape in root.findall(".//p:sp", XML_NS):
                    properties = shape.find(".//p:cNvPr", XML_NS)
                    name = properties.attrib.get("name", "") if properties is not None else ""
                    if not name.startswith("ivt:") or shape.find("p:txBody", XML_NS) is None:
                        continue
                    element_id = name[4:].split("#", 1)[0]
                    if element_id in result:
                        raise TextIdentityError(f"duplicate PPT text object for element: {element_id}")
                    result[element_id] = _shape_text(shape)
    except (OSError, zipfile.BadZipFile, ET.ParseError, ValueError) as exc:
        raise TextIdentityError(f"cannot extract PPT text: {exc}") from exc
    return result


def layout_with_ppt_text(layout: dict[str, Any], pptx: Path) -> dict[str, Any]:
    extracted = extract_ppt_text_by_element(pptx)
    result = copy.deepcopy(layout)
    rewritten: list[dict[str, Any]] = []
    for element in result.get("elements", []):
        if element.get("type") != "text":
            rewritten.append(element)
            continue
        if element["id"] not in extracted:
            continue
        element["text"] = extracted[element["id"]]
        element.pop("runs", None)
        rewritten.append(element)
    result["elements"] = rewritten
    return result


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
