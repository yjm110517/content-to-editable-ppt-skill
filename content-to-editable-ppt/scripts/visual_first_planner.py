from __future__ import annotations

import copy
from typing import Any

from schema_utils import ContractError, error
from slide_size import validate_slide_ratio_compatible


SUPPORTED_CHART_TYPES = {"vertical_bar", "horizontal_bar", "line", "donut"}


def content_authority_from_handoff(handoff: dict[str, Any]) -> dict[str, Any]:
    return {
        "text_items": [
            {"id": item["id"], "text": item["text"]}
            for item in handoff["content"]["text_items"]
        ]
    }


def validate_content_projection(handoff: dict[str, Any], projection: dict[str, Any]) -> None:
    expected = content_authority_from_handoff(handoff)
    if projection != expected:
        raise ContractError([
            error(
                "$.source-content.json",
                "source-content.json does not match the Handoff content projection",
                "content_projection_mismatch",
            )
        ])


def validate_block_against_handoff(block: dict[str, Any], handoff: dict[str, Any]) -> None:
    if block["scope"] != "objects":
        return
    known = {
        item["id"] for item in handoff["semantic_structure"]["objects"]
    } | {
        item["id"] for item in handoff["stage2"]["visual_objects"]
    }
    unknown = sorted(set(block["object_ids"]) - known)
    if unknown:
        raise ContractError([
            error(
                "$.block.object_ids",
                f"BLOCK references unknown object IDs: {', '.join(unknown)}",
                "unknown_reference",
            )
        ])


def validate_plan_against_handoff(
    plan: dict[str, Any],
    handoff: dict[str, Any],
    request: dict[str, Any],
    *,
    iteration: int,
    slide_id: str,
) -> None:
    failures: list[dict[str, str]] = []
    if plan["page"]["id"] != slide_id or slide_id != handoff["slide_id"]:
        failures.append(error("$.page.id", "Plan, call, and Handoff slide IDs must match", "page_identity_mismatch"))
    if plan["page"]["iteration"] != iteration:
        failures.append(error("$.page.iteration", "Plan iteration does not match the call", "iteration_mismatch"))
    if plan["source"]["approved_design"] != handoff["stage2"]["approved_design"] or plan["source"]["approved_design"] != request["source_image"]:
        failures.append(error("$.source.approved_design", "Plan Approved Design must match Handoff and Request", "source_mismatch"))
    try:
        validate_slide_ratio_compatible(
            request["output_ratio"],
            plan["slide"]["width_in"],
            plan["slide"]["height_in"],
        )
    except ContractError as exc:
        failures.extend(exc.errors)

    elements = {item["id"]: item for item in plan["elements"]}
    authority_objects = {item["id"]: item for item in handoff["semantic_structure"]["objects"]}
    visual_objects = {item["id"]: item for item in handoff["stage2"]["visual_objects"]}
    relations = {item["id"]: item for item in handoff["semantic_structure"]["relations"]}
    structured_data = {item["id"]: item for item in handoff["structured_data"]}

    expected_representations = {
        "text": {"native_text"},
        "shape": {"native_shape"},
        "connector": {"native_connector"},
        "chart": {"native_chart"},
        "table": {"native_table"},
        "visual_placeholder": {"native_shape", "raster_asset"},
    }
    for object_id, authority_object in authority_objects.items():
        kind = authority_object["kind"]
        element = elements.get(object_id)
        if element is None:
            failures.append(error("$.elements", f"required Stage 1 object is missing: {object_id}", "grounding_incomplete"))
            continue
        if element["representation"] not in expected_representations[kind]:
            failures.append(error(
                f"$.elements.{object_id}.representation",
                f"Stage 1 {kind} object uses an invalid representation",
                "representation_mismatch",
            ))
            continue
        if kind == "text" and element["content_ref"] != authority_object["content_ref"]:
            failures.append(error(f"$.elements.{object_id}.content_ref", "text content_ref must match Stage 1 Authority", "content_identity"))
        if kind in {"chart", "table"}:
            data_ref = authority_object["data_ref"]
            data = structured_data.get(data_ref)
            if data is None:
                failures.append(error(f"$.semantic_structure.objects.{object_id}.data_ref", "required structured data is missing", "missing_structured_data"))
            elif data["kind"] != kind:
                failures.append(error(f"$.semantic_structure.objects.{object_id}.data_ref", "structured data kind does not match object kind", "data_type_mismatch"))
            if element["data_ref"] != data_ref:
                failures.append(error(f"$.elements.{object_id}.data_ref", "data_ref must match Stage 1 Authority", "data_identity_mismatch"))
            if kind == "chart" and data and data.get("chart_type"):
                if data["chart_type"] not in SUPPORTED_CHART_TYPES:
                    failures.append(error(f"$.semantic_structure.objects.{object_id}.data_ref", "Stage 1 chart type is not supported by the current Builder", "unsupported_reconstruction"))
                elif element["style"]["chart_type"] != data["chart_type"]:
                    failures.append(error(f"$.elements.{object_id}.style.chart_type", "chart type must match Stage 1 Authority", "data_identity_mismatch"))
        if kind == "connector":
            relation = relations[authority_object["relation_ref"]]
            if element["from_id"] != relation["from_id"] or element["to_id"] != relation["to_id"]:
                failures.append(error(f"$.elements.{object_id}", "connector endpoints must match its Stage 1 relation", "topology_mismatch"))

    for object_id in visual_objects:
        element = elements.get(object_id)
        if element is None:
            failures.append(error("$.elements", f"required Stage 2 visual object is missing: {object_id}", "grounding_incomplete"))
        elif element["representation"] not in {"native_shape", "raster_asset"}:
            failures.append(error(
                f"$.elements.{object_id}.representation",
                "Stage 2 visual objects require native_shape or raster_asset",
                "representation_mismatch",
            ))

    required_ids = set(authority_objects) | set(visual_objects)
    for element_id, element in elements.items():
        if element_id in required_ids:
            continue
        if element["representation"] not in {"native_shape", "raster_asset"}:
            failures.append(error(
                f"$.elements.{element_id}.representation",
                "additional decoration requires native_shape or raster_asset",
                "representation_mismatch",
            ))

    if failures:
        raise ContractError(failures)


def canonicalize_plan_for_runtime(plan: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    """Return a Canonical Plan without mutating the Planner's raw candidate."""

    canonical = copy.deepcopy(plan)
    expected = validate_slide_ratio_compatible(
        request["output_ratio"],
        plan["slide"]["width_in"],
        plan["slide"]["height_in"],
    )
    canonical["slide"]["width_in"] = expected["width_in"]
    canonical["slide"]["height_in"] = expected["height_in"]
    return canonical
