from __future__ import annotations

from decimal import Decimal
import posixpath
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def object_name(shape: ET.Element) -> str:
    item = shape.find(".//p:cNvPr", NS)
    return item.attrib.get("name", "") if item is not None else ""


def base_id(name: str) -> str:
    return name[4:].split("#", 1)[0]


def native_type(shape: ET.Element) -> str | None:
    if shape.tag == f"{{{NS['p']}}}pic":
        return "image"
    if shape.tag == f"{{{NS['p']}}}cxnSp":
        return "line"
    if shape.tag == f"{{{NS['p']}}}graphicFrame":
        if shape.find(".//c:chart", NS) is not None:
            return "chart"
        if shape.find(".//a:tbl", NS) is not None:
            return "table"
        return "graphic"
    if shape.tag == f"{{{NS['p']}}}sp":
        return "text" if shape.find("p:txBody", NS) is not None else "shape"
    return None


def _slide_relationships(archive: zipfile.ZipFile, slide_index: int) -> dict[str, str]:
    path = f"ppt/slides/_rels/slide{slide_index}.xml.rels"
    if path not in archive.namelist():
        return {}
    root = ET.fromstring(archive.read(path))
    result: dict[str, str] = {}
    for relation in root.findall("pr:Relationship", NS):
        target = relation.attrib.get("Target", "")
        resolved = posixpath.normpath(posixpath.join("ppt/slides", target))
        result[relation.attrib["Id"]] = resolved.lstrip("/")
    return result


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(value.text or "" for value in node.findall(".//a:t", NS))


def _chart_points(node: ET.Element | None) -> list[str]:
    if node is None:
        return []
    points = node.findall(".//c:pt", NS)
    return [point.findtext("c:v", default="", namespaces=NS) for point in points]


def chart_signature(archive: zipfile.ZipFile, slide_index: int, shape: ET.Element) -> dict[str, Any] | None:
    chart = shape.find(".//c:chart", NS)
    if chart is None:
        return None
    relation_id = chart.attrib.get(f"{{{NS['r']}}}id")
    target = _slide_relationships(archive, slide_index).get(relation_id or "")
    if not target or target not in archive.namelist():
        return None
    root = ET.fromstring(archive.read(target))
    plot_area = root.find(".//c:plotArea", NS)
    plot = next(
        (
            child for child in list(plot_area) if child.tag.rsplit("}", 1)[-1]
            in {"barChart", "lineChart", "doughnutChart"}
        ),
        None,
    ) if plot_area is not None else None
    chart_type = plot.tag.rsplit("}", 1)[-1] if plot is not None else ""
    bar_direction = None
    if plot is not None:
        direction = plot.find("c:barDir", NS)
        bar_direction = direction.attrib.get("val") if direction is not None else None
    series = plot.findall("c:ser", NS) if plot is not None else []
    categories = _chart_points(series[0].find("c:cat", NS)) if series else []
    return {
        "chart_type": chart_type,
        "bar_direction": bar_direction,
        "categories": categories,
        "series": [
            {
                "name": series_item.findtext(".//c:tx//c:v", default="", namespaces=NS),
                "values": [str(Decimal(value)) for value in _chart_points(series_item.find("c:val", NS))],
            }
            for series_item in series
        ],
    }


def chart_layout_signature(element: dict[str, Any]) -> dict[str, Any]:
    return {
        "chart_type": {"vertical_bar": "barChart", "horizontal_bar": "barChart", "line": "lineChart", "donut": "doughnutChart"}[element["chart_type"]],
        "bar_direction": {"vertical_bar": "col", "horizontal_bar": "bar"}.get(element["chart_type"]),
        "categories": [str(value) for value in element["categories"]],
        "series": [
            {
                "name": item["name"],
                "values": [str(Decimal(value) / Decimal(element["value_scale"])) for value in item["values"]],
            }
            for item in element["series"]
        ],
    }


def table_signature(shape: ET.Element) -> dict[str, Any] | None:
    table = shape.find(".//a:tbl", NS)
    if table is None:
        return None
    grid = table.findall("a:tblGrid/a:gridCol", NS)
    rows: list[list[dict[str, Any]]] = []
    for row in table.findall("a:tr", NS):
        current: list[dict[str, Any]] = []
        for cell in row.findall("a:tc", NS):
            properties = cell.find("a:tcPr", NS)
            attrs = {**cell.attrib, **(properties.attrib if properties is not None else {})}
            if attrs.get("hMerge") in {"1", "true"} or attrs.get("vMerge") in {"1", "true"}:
                continue
            fill = properties.find("a:solidFill/a:srgbClr", NS) if properties is not None else None
            run = cell.find(".//a:rPr", NS)
            current.append({
                "text": _text(cell),
                "row_span": int(attrs.get("rowSpan", "1")),
                "column_span": int(attrs.get("gridSpan", "1")),
                "h_merge": attrs.get("hMerge") == "1",
                "v_merge": attrs.get("vMerge") == "1",
                "fill": fill.attrib.get("val") if fill is not None else None,
                "bold": run is not None and run.attrib.get("b") == "1",
            })
        rows.append(current)
    return {"column_count": len(grid), "rows": rows}


def table_layout_signature(element: dict[str, Any]) -> dict[str, Any]:
    anchors = {(item["row"], item["column"]): item for item in element["merges"]}
    covered = {
        (row, column)
        for item in element["merges"]
        for row in range(item["row"], item["row"] + item["row_span"])
        for column in range(item["column"], item["column"] + item["column_span"])
        if (row, column) != (item["row"], item["column"])
    }
    rows: list[list[dict[str, Any]]] = []
    for row_index, row in enumerate(element["grid"]):
        current = []
        for column_index, value in enumerate(row):
            if (row_index, column_index) in covered:
                continue
            merge = anchors.get((row_index, column_index), {})
            current.append({
                "text": value,
                "row_span": merge.get("row_span", 1),
                "column_span": merge.get("column_span", 1),
                "header": row_index < element["header_row_count"],
            })
        rows.append(current)
    return {"column_count": len(element["grid"][0]), "rows": rows}


def native_data_signatures(path: Path) -> dict[str, dict[str, Any]]:
    """Return stable-ID keyed Chart/Table signatures from every slide in a PPTX.

    The result deliberately excludes package-local relationship IDs and chart
    part filenames so it can compare a PptxGenJS build with PowerPoint SaveAs.
    """

    signatures: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        slide_names = sorted(
            (name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")),
            key=lambda name: int(Path(name).stem.removeprefix("slide")),
        )
        for slide_index, slide_name in enumerate(slide_names, start=1):
            root = ET.fromstring(archive.read(slide_name))
            tree = root.find(".//p:spTree", NS)
            if tree is None:
                continue
            for shape in list(tree):
                name = object_name(shape)
                if not name.startswith("ivt:"):
                    continue
                kind = native_type(shape)
                if kind == "chart":
                    signature = chart_signature(archive, slide_index, shape)
                elif kind == "table":
                    signature = table_signature(shape)
                else:
                    continue
                if signature is None:
                    continue
                signatures[name] = {"type": kind, "signature": signature}
    return signatures
