from __future__ import annotations

import copy
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, TypedDict

from schema_utils import ContractError, error
from slide_size import resolve_slide_size


ASPECT_TOLERANCE = Decimal("0.05")
ASPECT_EPSILON = Decimal("0.000000001")
SLIDE_SIZE_TOLERANCE = Decimal("0.000001")


class SourceMetadata(TypedDict):
    width_px: int
    height_px: int


class CompiledArtifacts(TypedDict):
    layout: dict[str, Any]
    crops: dict[str, Any]
    asset_manifest: dict[str, Any]


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _inches(value: Any, extent: Any) -> float:
    return float((_decimal(value) * _decimal(extent)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _pixel(value: Any, extent: int) -> int:
    return int((_decimal(value) * Decimal(extent)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _legacy_geometry(geometry: dict[str, Any], slide: dict[str, Any]) -> dict[str, float]:
    return {
        "x": _inches(geometry["x"], slide["width_in"]),
        "y": _inches(geometry["y"], slide["height_in"]),
        "w": _inches(geometry["width"], slide["width_in"]),
        "h": _inches(geometry["height"], slide["height_in"]),
    }


def _crop_box(region: dict[str, Any], source: SourceMetadata, path: str) -> list[int]:
    left = _pixel(region["x"], source["width_px"])
    top = _pixel(region["y"], source["height_px"])
    right = _pixel(_decimal(region["x"]) + _decimal(region["width"]), source["width_px"])
    bottom = _pixel(_decimal(region["y"]) + _decimal(region["height"]), source["height_px"])
    if left < 0 or top < 0 or right > source["width_px"] or bottom > source["height_px"] or right <= left or bottom <= top:
        raise ContractError([error(path, "rounded crop box is empty or out of bounds", "invalid_crop_box")])
    return [left, top, right, bottom]


def _validate_aspect(box: list[int], geometry: dict[str, Any], slide: dict[str, Any], path: str) -> None:
    source_aspect = Decimal(box[2] - box[0]) / Decimal(box[3] - box[1])
    target_width = _decimal(geometry["width"]) * _decimal(slide["width_in"])
    target_height = _decimal(geometry["height"]) * _decimal(slide["height_in"])
    target_aspect = target_width / target_height
    relative_error = abs(source_aspect - target_aspect) / target_aspect
    if relative_error > ASPECT_TOLERANCE + ASPECT_EPSILON:
        raise ContractError([error(path, f"source and placement aspect ratios differ by {relative_error:.6f}", "asset_aspect_mismatch")])


def _authority_index(content_authority: dict[str, Any]) -> dict[str, str]:
    items = content_authority.get("text_items")
    failures: list[dict[str, str]] = []
    if not isinstance(items, list) or not items:
        raise ContractError([error("$.text_items", "content authority requires a non-empty text_items array", "content_authority")])
    result: dict[str, str] = {}
    for index, item in enumerate(items):
        base = f"$.text_items[{index}]"
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            failures.append(error(base + ".id", "authority item requires a non-empty string id", "content_authority"))
            continue
        if item["id"] in result:
            failures.append(error(base + ".id", f"duplicate authority id: {item['id']}", "duplicate_content_ref"))
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text:
            failures.append(error(base + ".text", "authority text must be a non-empty string", "content_authority"))
            continue
        result[item["id"]] = text
    if failures:
        raise ContractError(failures)
    return result


def _structured_data_index(authority: dict[str, Any] | Iterable[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if authority is None:
        return {}
    items = authority.get("structured_data") if isinstance(authority, dict) else authority
    if not isinstance(items, Iterable) or isinstance(items, (str, bytes, dict)):
        raise ContractError([error("$.structured_data", "structured data authority requires an array", "missing_structured_data")])
    result: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    for index, item in enumerate(items):
        base = f"$.structured_data[{index}]"
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            failures.append(error(base + ".id", "structured data item requires a non-empty id", "missing_structured_data"))
            continue
        if item["id"] in result:
            failures.append(error(base + ".id", f"duplicate structured data id: {item['id']}", "duplicate_data_ref"))
            continue
        result[item["id"]] = item
    if failures:
        raise ContractError(failures)
    return result


def _decimal_scale(values: Iterable[Any]) -> int:
    decimals = [_decimal(value) for value in values]
    places = max((-value.as_tuple().exponent for value in decimals), default=0)
    return 10 ** max(0, places)


def _normalize_table_data(data: dict[str, Any]) -> tuple[list[list[Any]], int, list[dict[str, int]]]:
    if "grid" in data:
        return copy.deepcopy(data["grid"]), data["header_row_count"], copy.deepcopy(data["merges"])
    return [list(data["columns"]), *copy.deepcopy(data["rows"])], 1, []


def _format_table_cell(value: Any, number_format: str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) and number_format:
        match = re.fullmatch(r"0\.(0+)", number_format)
        if match:
            places = len(match.group(1))
            return f"{_decimal(value):.{places}f}"
    return str(value)


def _normalized_lengths(ratios: list[Any] | None, count: int, extent: float) -> list[float]:
    values = [_decimal(value) for value in ratios] if ratios is not None else [Decimal(1)] * count
    if len(values) != count or any(value <= 0 for value in values):
        raise ContractError([error("$.style", "table size ratios must be positive and match the authority grid", "structured_data_shape")])
    total = sum(values)
    return [float((value / total * _decimal(extent)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) for value in values]


def _validate_slide_ratio(request: dict[str, Any], slide: dict[str, Any]) -> None:
    expected = resolve_slide_size(request["output_ratio"])
    width_error = abs(_decimal(slide["width_in"]) - _decimal(expected["width_in"]))
    height_error = abs(_decimal(slide["height_in"]) - _decimal(expected["height_in"]))
    if width_error > SLIDE_SIZE_TOLERANCE or height_error > SLIDE_SIZE_TOLERANCE:
        raise ContractError([
            error(
                "$.slide",
                (
                    f"slide size {slide['width_in']} x {slide['height_in']} does not match "
                    f"Runtime policy {expected['width_in']} x {expected['height_in']} for {request['output_ratio']}"
                ),
                "slide_ratio_mismatch",
            )
        ])


def compile_reconstruction_plan(
    plan: dict[str, Any],
    content_authority: dict[str, Any],
    request: dict[str, Any],
    source_metadata: SourceMetadata,
    structured_data_authority: dict[str, Any] | Iterable[dict[str, Any]] | None = None,
) -> CompiledArtifacts:
    failures: list[dict[str, str]] = []
    authority = _authority_index(content_authority)
    structured_data = _structured_data_index(structured_data_authority)
    if request.get("source_image") != plan["source"]["approved_design"]:
        failures.append(error("$.source.approved_design", "must match request.source_image", "source_mismatch"))
    if not isinstance(source_metadata.get("width_px"), int) or source_metadata["width_px"] < 1:
        failures.append(error("$.source_metadata.width_px", "actual image width must be positive", "source_metadata"))
    if not isinstance(source_metadata.get("height_px"), int) or source_metadata["height_px"] < 1:
        failures.append(error("$.source_metadata.height_px", "actual image height must be positive", "source_metadata"))

    content_elements: dict[str, int] = {}
    data_elements: dict[str, int] = {}
    for index, item in enumerate(plan["elements"]):
        if item["representation"] != "native_text":
            continue
        content_ref = item["content_ref"]
        if content_ref not in authority:
            failures.append(error(f"$.elements[{index}].content_ref", f"unknown content_ref: {content_ref}", "unknown_content_ref"))
        if content_ref in content_elements:
            failures.append(error(f"$.elements[{index}].content_ref", f"duplicate content_ref: {content_ref}", "duplicate_content_ref"))
        content_elements[content_ref] = index

    for index, item in enumerate(plan["elements"]):
        if item["representation"] not in {"native_chart", "native_table"}:
            continue
        data_ref = item["data_ref"]
        data = structured_data.get(data_ref)
        expected_kind = "chart" if item["representation"] == "native_chart" else "table"
        if data is None:
            failures.append(error(f"$.elements[{index}].data_ref", f"missing structured data: {data_ref}", "missing_structured_data"))
        elif data.get("kind") != expected_kind:
            failures.append(error(f"$.elements[{index}].data_ref", f"{item['representation']} requires {expected_kind} data", "data_type_mismatch"))
        if data_ref in data_elements:
            failures.append(error(f"$.elements[{index}].data_ref", f"duplicate data_ref: {data_ref}", "duplicate_data_ref"))
        data_elements[data_ref] = index
    for content_ref in authority:
        if content_ref not in content_elements:
            failures.append(error("$.elements", f"authority item is not consumed: {content_ref}", "missing_content_ref"))
    if failures:
        raise ContractError(failures)

    slide = plan["slide"]
    _validate_slide_ratio(request, slide)
    layout_elements: list[dict[str, Any]] = []
    crops: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []

    has_data_objects = any(item["representation"] in {"native_chart", "native_table"} for item in plan["elements"])
    for index, item in enumerate(plan["elements"]):
        base = {"id": item["id"], **_legacy_geometry(item["geometry"], slide), "z_index": item["z_index"]}
        representation = item["representation"]
        if representation == "native_text":
            layout_elements.append({
                **base,
                "type": "text",
                "editable": True,
                "text": authority[item["content_ref"]],
                "content_ref": item["content_ref"],
                "segment_order": 0,
                "joiner": "",
                "editability_required": True,
                **copy.deepcopy(item["style"]),
            })
        elif representation == "native_shape":
            style = copy.deepcopy(item["style"])
            shape = style.pop("shape")
            layout_elements.append({**base, "type": "shape", "editable": True, "shape": shape, **style})
        elif representation == "native_connector":
            layout_elements.append({
                **base,
                "type": "line",
                "editable": True,
                "from_id": item["from_id"],
                "to_id": item["to_id"],
                **copy.deepcopy(item["style"]),
            })
        elif representation == "raster_asset":
            box = _crop_box(item["asset_request"]["source_region"], source_metadata, f"$.elements[{index}].asset_request.source_region")
            _validate_aspect(box, item["geometry"], slide, f"$.elements[{index}].asset_request.source_region")
            output = f"{item['id']}.png"
            layout_elements.append({
                **base,
                "type": "image",
                "editable": False,
                "asset_id": item["id"],
                "fit": "contain",
                "preserve_aspect_ratio": True,
                "rounding": False,
                "contains_text": False,
                "text_editability_exempt": False,
                "alt_text": item["role"],
            })
            crops.append({"id": item["id"], "output": output, "box_px": box, "padding_px": 0, "mode": "rgba", "remove_background": False})
            assets.append({
                "id": item["id"],
                "type": "png",
                "path": f"assets/{output}",
                "source": "cropped",
                "recolorable": False,
                "contains_text": False,
                "text_editability_exempt": False,
                "security_status": "pending",
            })
        elif representation == "native_chart":
            data = structured_data[item["data_ref"]]
            values = [value for series in data["series"] for value in series["values"]]
            scale = _decimal_scale(values)
            style = copy.deepcopy(item["style"])
            if "color_tokens" in style:
                style["color_tokens"] = [value.replace("#", "").upper() for value in style["color_tokens"]]
            layout_elements.append({
                **base,
                "type": "chart",
                "editable": True,
                "data_ref": item["data_ref"],
                "chart_type": style.pop("chart_type"),
                "categories": [str(value) for value in data["categories"]],
                "series": [
                    {
                        "name": series["name"],
                        "values": [int((_decimal(value) * scale).to_integral_exact()) for value in series["values"]],
                    }
                    for series in data["series"]
                ],
                "value_scale": scale,
                **style,
                **{field: data[field] for field in ("category_axis_label", "value_axis_label", "unit") if field in data},
            })
        elif representation == "native_table":
            data = structured_data[item["data_ref"]]
            grid, header_row_count, merges = _normalize_table_data(data)
            style = copy.deepcopy(item["style"])
            number_format = style.get("number_format")
            layout_elements.append({
                **base,
                "type": "table",
                "editable": True,
                "data_ref": item["data_ref"],
                "grid": [[_format_table_cell(value, number_format) for value in row] for row in grid],
                "header_row_count": header_row_count,
                "merges": merges,
                "column_widths": _normalized_lengths(style.pop("column_width_ratios", None), len(grid[0]), base["w"]),
                "row_heights": _normalized_lengths(style.pop("row_height_ratios", None), len(grid), base["h"]),
                **style,
            })
        else:
            raise ContractError([error(f"$.elements[{index}].representation", f"P1 does not support {representation}", "unsupported_representation")])

    layout = {
        "schema_version": "1.5" if has_data_objects else "1.4",
        "request": "request.json",
        "source": {"image": plan["source"]["approved_design"], **source_metadata},
        "slide": copy.deepcopy(slide),
        "metadata": {
            "topic": request["topic"],
            "iteration": plan["page"]["iteration"],
            "typography_interaction": request["typography_interaction"],
            "page_id": plan["page"]["id"],
        },
        "asset_manifest": "asset_manifest.json",
        "styles": {},
        "elements": layout_elements,
    }
    return {
        "layout": layout,
        "crops": {"schema_version": "1.3", "source": plan["source"]["approved_design"], "assets": crops},
        "asset_manifest": {"schema_version": "1.3", "assets": assets},
    }
