from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


SCHEMA_VERSION = "1.3"
SCHEMA_FILES = {
    "request": "request.schema.json",
    "layout": "layout.schema.json",
    "crops": "crops.schema.json",
    "asset_manifest": "asset-manifest.schema.json",
    "qa_report": "qa-report.schema.json",
    "review_report": "review-report.schema.json",
    "review_evaluation": "review-evaluation.schema.json",
    "review_patch": "review-patch.schema.json",
    "revision_patch": "revision-patch.schema.json",
    "run_state": "run-state.schema.json",
    "delivery_decision": "delivery-decision.schema.json",
    "build_summary": "build-summary.schema.json",
    "font_audit": "font-audit.schema.json",
    "render_report": "render-report.schema.json",
    "agent_role": "agent-role.schema.json",
    "agent_call_record": "agent-call-record.schema.json",
    "planner_response": "planner-response.schema.json",
    "reviewer_response": "reviewer-response.schema.json",
    "runtime_manifest": "runtime-manifest.schema.json",
    "runtime_error": "runtime-error.schema.json",
    "reviewer_technical_failure": "reviewer-technical-failure.schema.json",
    "content_authority_report": "content-authority-report.schema.json",
    "issue_attribution": "issue-attribution.schema.json",
    "text_identity_map": "text-identity-map.schema.json",
    "deck_build_request": "deck-build-request.schema.json",
    "powerpoint_roundtrip_report": "powerpoint-roundtrip-report.schema.json",
    "reviewer_model_identity": "reviewer-model-identity.schema.json",
    "reconstruction_plan": "reconstruction-plan.schema.json",
    "stage1_authority": "stage1-authority.schema.json",
    "stage2_handoff": "stage2-handoff.schema.json",
    "reconstruction_handoff": "reconstruction-handoff.schema.json",
}

SUPPORTED_SCHEMA_VERSIONS = {
    "agent_call_record": {"1.3", "1.4"},
    "revision_patch": {"1.0"},
    "layout": {"1.3", "1.4", "1.5"},
    "run_state": {"1.3", "1.4"},
    "runtime_manifest": {"1.0", "1.1"},
    "runtime_error": {"1.0"},
    "reviewer_technical_failure": {"1.0"},
    "content_authority_report": {"1.0"},
    "issue_attribution": {"1.0"},
    "text_identity_map": {"1.0"},
    "deck_build_request": {"1.0"},
    "powerpoint_roundtrip_report": {"1.0"},
    "reviewer_model_identity": {"1.0"},
    "reconstruction_plan": {"1.0", "1.1", "1.2"},
    "stage1_authority": {"1.0", "1.1"},
    "stage2_handoff": {"1.0"},
    "reconstruction_handoff": {"1.0", "1.1"},
    "build_summary": {"1.3", "1.4"},
    "qa_report": {"1.3", "1.4"},
    "planner_response": {"1.4", "1.5"},
    "asset_manifest": {"1.3", "1.4"},
}


class ContractError(ValueError):
    def __init__(self, errors: Iterable[dict[str, Any]]):
        self.errors = list(errors)
        super().__init__("; ".join(error["message"] for error in self.errors))


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ContractError([error("$", "document must be a JSON object")])
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise ContractError([error("$", "document must be a YAML object")])
    return value


def error(path: str, message: str, code: str = "semantic_error") -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def json_path(parts: Iterable[Any]) -> str:
    result = "$"
    for part in parts:
        result += f"[{part}]" if isinstance(part, int) else f".{part}"
    return result


def validate_schema(kind: str, document: dict[str, Any], schema_dir: Path) -> None:
    schema_path = schema_dir / SCHEMA_FILES[kind]
    schema = load_json(schema_path)
    resources = []
    for filename in SCHEMA_FILES.values():
        candidate = schema_dir / filename
        if candidate.is_file():
            candidate_schema = load_json(candidate)
            if candidate_schema.get("$id"):
                resources.append((candidate_schema["$id"], Resource.from_contents(candidate_schema)))
    validator = Draft202012Validator(schema, registry=Registry().with_resources(resources))
    failures = [
        error(json_path(item.absolute_path), item.message, "schema_error")
        for item in sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    ]
    if failures:
        raise ContractError(failures)


def is_safe_relative_path(value: str, *, filename_only: bool = False) -> bool:
    if not value or "\\" in value or ":" in value or "\x00" in value:
        return False
    candidate = PurePosixPath(value)
    if not candidate.parts or candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts:
        return False
    if filename_only and len(candidate.parts) != 1:
        return False
    if any(part.endswith((" ", ".")) for part in candidate.parts):
        return False
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    return all(part.split(".", 1)[0].upper() not in reserved for part in candidate.parts)


def _is_utc_timestamp(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return value.endswith("Z") and parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def _unique(items: list[dict[str, Any]], key: str, base: str, errors: list[dict[str, str]]) -> None:
    seen: set[Any] = set()
    for index, item in enumerate(items):
        value = item.get(key)
        if value in seen:
            errors.append(error(f"{base}[{index}].{key}", f"duplicate {key}: {value}"))
        seen.add(value)


def _region_ok(region: dict[str, Any]) -> bool:
    return region["x"] + region["w"] <= 1 and region["y"] + region["h"] <= 1


def _validate_stage1_authority(document: dict[str, Any], failures: list[dict[str, str]]) -> None:
    slides = document["slides"]
    _unique(slides, "slide_id", "$.slides", failures)
    _unique(slides, "order", "$.slides", failures)
    orders = sorted(slide["order"] for slide in slides)
    if orders != list(range(1, len(slides) + 1)):
        failures.append(error("$.slides", "slide order must be unique and contiguous from 1", "invalid_slide_order"))

    for slide_index, slide in enumerate(slides):
        base = f"$.slides[{slide_index}]"
        if not is_safe_relative_path(slide["wireframe"]["path"]):
            failures.append(error(base + ".wireframe.path", "wireframe path must be a safe relative path", "unsafe_path"))

        text_items = slide["text_items"]
        objects = slide["objects"]
        structured_data = slide["structured_data"]
        structure = slide["semantic_structure"]
        _unique(text_items, "id", base + ".text_items", failures)
        _unique(objects, "id", base + ".objects", failures)
        _unique(structured_data, "id", base + ".structured_data", failures)
        _unique(structure["regions"], "id", base + ".semantic_structure.regions", failures)
        _unique(structure["relations"], "id", base + ".semantic_structure.relations", failures)

        text_ids = {item["id"] for item in text_items}
        object_ids = {item["id"] for item in objects}
        data_by_id = {item["id"]: item for item in structured_data}
        relations_by_id = {item["id"]: item for item in structure["relations"]}

        for object_index, item in enumerate(objects):
            item_base = f"{base}.objects[{object_index}]"
            if item["kind"] == "text" and item["content_ref"] not in text_ids:
                failures.append(error(item_base + ".content_ref", f"unknown content_ref: {item['content_ref']}", "unknown_content_ref"))
            if item["kind"] in {"chart", "table"}:
                data = data_by_id.get(item["data_ref"])
                if data is None or data["kind"] != item["kind"]:
                    failures.append(error(item_base + ".data_ref", f"unknown or incompatible data_ref: {item['data_ref']}", "unknown_data_ref"))
            if item["kind"] == "connector" and item["relation_ref"] not in relations_by_id:
                failures.append(error(item_base + ".relation_ref", f"unknown relation_ref: {item['relation_ref']}", "unknown_relation_ref"))

        for region_index, region in enumerate(structure["regions"]):
            for member_index, member in enumerate(region["members"]):
                if member not in object_ids:
                    failures.append(error(
                        f"{base}.semantic_structure.regions[{region_index}].members[{member_index}]",
                        f"unknown object reference: {member}",
                        "unknown_reference",
                    ))

        seen_reading: set[str] = set()
        for order_index, object_id in enumerate(structure["reading_order"]):
            path = f"{base}.semantic_structure.reading_order[{order_index}]"
            if object_id in seen_reading:
                failures.append(error(path, f"duplicate reading order object: {object_id}", "duplicate_reference"))
            elif object_id not in object_ids:
                failures.append(error(path, f"unknown object reference: {object_id}", "unknown_reference"))
            seen_reading.add(object_id)

        for relation_index, relation in enumerate(structure["relations"]):
            relation_base = f"{base}.semantic_structure.relations[{relation_index}]"
            if relation["from_id"] == relation["to_id"]:
                failures.append(error(relation_base, "relation cannot reference the same object twice", "self_reference"))
            for field in ("from_id", "to_id"):
                if relation[field] not in object_ids:
                    failures.append(error(relation_base + f".{field}", f"unknown object reference: {relation[field]}", "unknown_reference"))

        for data_index, data in enumerate(structured_data):
            data_base = f"{base}.structured_data[{data_index}]"
            if document["schema_version"] == "1.0" and (
                (data["kind"] == "table" and "grid" in data)
                or (data["kind"] == "chart" and any(field in data for field in ("chart_type", "category_axis_label", "value_axis_label", "unit")))
            ):
                failures.append(error(data_base, "Stage 1 Authority 1.0 does not support P4 structured data fields", "schema_version"))
            if data["kind"] == "chart":
                category_count = len(data["categories"])
                for series_index, series in enumerate(data["series"]):
                    if len(series["values"]) != category_count:
                        failures.append(error(
                            f"{data_base}.series[{series_index}].values",
                            "chart series length must match categories length",
                            "structured_data_shape",
                        ))
            elif "columns" in data:
                column_count = len(data["columns"])
                for row_index, row in enumerate(data["rows"]):
                    if len(row) != column_count:
                        failures.append(error(
                            f"{data_base}.rows[{row_index}]",
                            "table row length must match columns length",
                            "structured_data_shape",
                        ))
            else:
                grid = data["grid"]
                column_count = len(grid[0])
                if data["header_row_count"] > len(grid):
                    failures.append(error(data_base + ".header_row_count", "header row count exceeds grid rows", "structured_data_shape"))
                for row_index, row in enumerate(grid):
                    if len(row) != column_count:
                        failures.append(error(f"{data_base}.grid[{row_index}]", "table grid rows must have equal length", "structured_data_shape"))
                occupied: set[tuple[int, int]] = set()
                for merge_index, merge in enumerate(data["merges"]):
                    merge_base = f"{data_base}.merges[{merge_index}]"
                    row, column = merge["row"], merge["column"]
                    row_end, column_end = row + merge["row_span"], column + merge["column_span"]
                    if merge["row_span"] == 1 and merge["column_span"] == 1:
                        failures.append(error(merge_base, "table merge must span more than one cell", "structured_data_shape"))
                    if row_end > len(grid) or column_end > column_count:
                        failures.append(error(merge_base, "table merge exceeds grid bounds", "structured_data_shape"))
                        continue
                    if grid[row][column] is None:
                        failures.append(error(merge_base, "table merge anchor must contain a value", "structured_data_shape"))
                    for cell_row in range(row, row_end):
                        for cell_column in range(column, column_end):
                            key = (cell_row, cell_column)
                            if key in occupied:
                                failures.append(error(merge_base, "table merges must not overlap", "structured_data_shape"))
                            occupied.add(key)
                            if key != (row, column) and grid[cell_row][cell_column] is not None:
                                failures.append(error(merge_base, "covered table merge cells must be null", "structured_data_shape"))


def _validate_stage2_handoff(document: dict[str, Any], failures: list[dict[str, str]]) -> None:
    slides = document["slides"]
    _unique(slides, "slide_id", "$.slides", failures)
    for slide_index, slide in enumerate(slides):
        base = f"$.slides[{slide_index}]"
        for field in ("approved_design", "visual_spec"):
            if not is_safe_relative_path(slide[field]["path"]):
                failures.append(error(base + f".{field}.path", f"{field} path must be a safe relative path", "unsafe_path"))
        if not slide["visual_spec"]["path"].lower().endswith(".json"):
            failures.append(error(base + ".visual_spec.path", "visual spec must use a .json file", "invalid_visual_spec"))

        visual_objects = slide["visual_objects"]
        _unique(visual_objects, "id", base + ".visual_objects", failures)
        for object_index, item in enumerate(visual_objects):
            for overlap_index, overlap_id in enumerate(item["overlaps_with"]):
                path = f"{base}.visual_objects[{object_index}].overlaps_with[{overlap_index}]"
                if overlap_id == item["id"]:
                    failures.append(error(path, "visual object cannot overlap itself", "self_reference"))


def _validate_review_issues(document: dict[str, Any], failures: list[dict[str, str]]) -> None:
    _unique(document["issues"], "id", "$.issues", failures)
    issues_by_id = {item["id"]: item for item in document["issues"]}
    for index, item in enumerate(document["issues"]):
        base = f"$.issues[{index}]"
        if item["severity"] != "suggestion" and not (item["element_ids"] or item["asset_ids"] or "source_region" in item or "render_region" in item):
            failures.append(error(base, "non-suggestion issue requires an element, asset, or region"))
        for field in ("source_region", "render_region"):
            if field in item and not _region_ok(item[field]):
                failures.append(error(base + f".{field}", "normalized region exceeds page bounds"))
    for check_name, check in document["mandatory_visual_checks"].items():
        base = f"$.mandatory_visual_checks.{check_name}"
        if check["status"] == "fail":
            if not check["issue_ids"]:
                failures.append(error(base + ".issue_ids", "a failed mandatory visual check must reference at least one issue"))
            for issue_id in check["issue_ids"]:
                issue = issues_by_id.get(issue_id)
                if issue is None:
                    failures.append(error(base + ".issue_ids", f"unknown issue id: {issue_id}"))
                elif issue["severity"] == "suggestion":
                    failures.append(error(base + ".issue_ids", "a failed mandatory visual check cannot reference only a suggestion"))
        elif check["issue_ids"]:
            failures.append(error(base + ".issue_ids", "pass and not_applicable checks cannot reference issues"))
    failed_checks = [
        name for name, check in document["mandatory_visual_checks"].items()
        if check["status"] == "fail"
    ]
    if document["reviewer_recommendation"] == "pass" and failed_checks:
        failures.append(error("$.reviewer_recommendation", "pass is forbidden while a mandatory visual check fails"))


def validate_semantics(kind: str, document: dict[str, Any]) -> None:
    failures: list[dict[str, str]] = []
    supported_versions = SUPPORTED_SCHEMA_VERSIONS.get(kind, {SCHEMA_VERSION})
    if document.get("schema_version") not in supported_versions:
        failures.append(error("$.schema_version", f"expected one of {sorted(supported_versions)}"))

    if kind == "request":
        policy = document["review_policy"]
        if policy["warning_floor_score"] > policy["pass_score"]:
            failures.append(error("$.review_policy.warning_floor_score", "must not exceed pass_score"))
    elif kind == "stage1_authority":
        _validate_stage1_authority(document, failures)
    elif kind == "stage2_handoff":
        _validate_stage2_handoff(document, failures)
    elif kind == "reconstruction_handoff":
        approved_design = document["stage2"]["approved_design"]
        if not is_safe_relative_path(approved_design):
            failures.append(error(
                "$.stage2.approved_design",
                "approved design must be a safe work-root-relative path",
                "unsafe_path",
            ))
    elif kind == "reconstruction_plan":
        elements = document["elements"]
        _unique(elements, "id", "$.elements", failures)
        element_ids = {item["id"] for item in elements}
        supported = {"native_text", "native_shape", "native_connector", "raster_asset", "native_chart", "native_table"}
        for index, item in enumerate(elements):
            base = f"$.elements[{index}]"
            geometry = item["geometry"]
            if geometry["x"] + geometry["width"] > 1 or geometry["y"] + geometry["height"] > 1:
                failures.append(error(base + ".geometry", "normalized geometry exceeds page bounds", "geometry_out_of_bounds"))
            representation = item["representation"]
            if document["schema_version"] == "1.0" and representation in {"native_chart", "native_table"}:
                failures.append(error(base + ".representation", "Reconstruction Plan 1.0 does not support native data objects", "schema_version"))
            if representation not in supported:
                failures.append(error(base + ".representation", f"Runtime does not support {representation}", "unsupported_representation"))
            if representation == "native_connector":
                for field in ("from_id", "to_id"):
                    if item[field] not in element_ids:
                        failures.append(error(base + f".{field}", "unknown connection element id", "unknown_reference"))
                    elif item[field] == item["id"]:
                        failures.append(error(base + f".{field}", "connector cannot reference itself", "self_reference"))
            if representation == "raster_asset":
                source_region = item["asset_request"]["source_region"]
                if source_region["x"] + source_region["width"] > 1 or source_region["y"] + source_region["height"] > 1:
                    failures.append(error(base + ".asset_request.source_region", "normalized source region exceeds image bounds", "geometry_out_of_bounds"))
    elif kind == "layout":
        elements = document["elements"]
        _unique(elements, "id", "$.elements", failures)
        styles = document["styles"]
        width, height = document["slide"]["width_in"], document["slide"]["height_in"]
        element_ids = {item["id"] for item in elements}
        for index, item in enumerate(elements):
            base = f"$.elements[{index}]"
            if item["type"] != "line" and (item["w"] <= 0 or item["h"] <= 0):
                failures.append(error(base, "non-line elements require positive width and height"))
            if item["type"] == "line" and item["w"] == 0 and item["h"] == 0:
                failures.append(error(base, "line elements require non-zero width or height"))
            if not item.get("allow_overflow", False) and (item["x"] + item["w"] > width or item["y"] + item["h"] > height):
                failures.append(error(base, "element exceeds slide bounds"))
            if "style_ref" in item and item["style_ref"] not in styles:
                failures.append(error(base + ".style_ref", "unknown style reference"))
            if item["type"] == "shape" and not item.get("fill") and not item.get("line"):
                style = styles.get(item.get("style_ref", ""), {})
                if not style.get("fill") and not style.get("line"):
                    failures.append(error(base, "shape requires a visible fill or line"))
            if item["type"] == "text":
                if item.get("editability_required", True) is False and not item.get("exemption_reason"):
                    failures.append(error(base + ".exemption_reason", "non-required text requires an exemption reason"))
                style = styles.get(item.get("style_ref", ""), {})
                element_font = item.get("font_face", style.get("font_face"))
                element_size = item.get("font_size_pt", style.get("font_size_pt"))
                element_color = item.get("color", style.get("color"))
                runs = item.get("runs", [{"text": item.get("text", "")}])
                for run_index, run in enumerate(runs):
                    if not run.get("font_face", element_font):
                        failures.append(error(f"{base}.runs[{run_index}].font_face", "font_face is unresolved after style inheritance"))
                    if not run.get("font_size_pt", element_size):
                        failures.append(error(f"{base}.runs[{run_index}].font_size_pt", "font_size_pt is unresolved after style inheritance"))
                    if not run.get("color", element_color):
                        failures.append(error(f"{base}.runs[{run_index}].color", "color is unresolved after style inheritance"))
            if item["type"] == "line":
                for field in ("from_id", "to_id"):
                    if item.get(field) and item[field] not in element_ids:
                        failures.append(error(base + f".{field}", "unknown connection element id"))
            if item["type"] == "table":
                if document["schema_version"] != "1.5":
                    failures.append(error(base + ".type", "table elements require layout schema 1.5", "schema_version"))
                grid = item["grid"]
                width_count = len(grid[0])
                if any(len(row) != width_count for row in grid):
                    failures.append(error(base + ".grid", "table grid rows must have equal length", "structured_data_shape"))
                if len(item["column_widths"]) != width_count or len(item["row_heights"]) != len(grid):
                    failures.append(error(base, "table dimensions must match grid", "structured_data_shape"))
                if item["header_row_count"] > len(grid):
                    failures.append(error(base + ".header_row_count", "table header rows exceed grid", "structured_data_shape"))
    elif kind == "crops":
        assets = document["assets"]
        _unique(assets, "id", "$.assets", failures)
        _unique(assets, "output", "$.assets", failures)
        if not is_safe_relative_path(document["source"]):
            failures.append(error("$.source", "unsafe relative source path"))
        for index, item in enumerate(assets):
            left, top, right, bottom = item["box_px"]
            if right <= left or bottom <= top:
                failures.append(error(f"$.assets[{index}].box_px", "crop box must be non-empty"))
            if not is_safe_relative_path(item["output"], filename_only=True):
                failures.append(error(f"$.assets[{index}].output", "unsafe output filename"))
    elif kind == "asset_manifest":
        assets = document["assets"]
        _unique(assets, "id", "$.assets", failures)
        _unique(assets, "path", "$.assets", failures)
        for index, item in enumerate(assets):
            base = f"$.assets[{index}]"
            if not is_safe_relative_path(item["path"]):
                failures.append(error(base + ".path", "unsafe asset path"))
            if item["contains_text"] and not item["text_editability_exempt"]:
                failures.append(error(base, "text-bearing assets require an editability exemption"))
    elif kind in {"review_report", "reviewer_response"}:
        _validate_review_issues(document, failures)
    elif kind == "review_patch":
        if document["to_iteration"] != document["from_iteration"] + 1:
            failures.append(error("$.to_iteration", "must equal from_iteration + 1"))
        for index, operation in enumerate(document["operations"]):
            base = f"$.operations[{index}]"
            changes = operation["changes"]
            if operation["type"] == "update_element" and ({"id", "type"} & set(changes)):
                failures.append(error(base + ".changes", "update_element cannot change id or type"))
            if operation["type"] == "replace_asset" and "generated_svg" in changes:
                generated = changes["generated_svg"]
                content = generated["content"]
                if len(content.encode("utf-8")) > 1024 * 1024:
                    failures.append(error(base + ".changes.generated_svg.content", "generated SVG exceeds 1 MiB"))
                if "\x00" in content or re.search(r"(?is)<(?:script|foreignObject|text|tspan|textPath)\b|(?:href|xlink:href)\s*=\s*['\"](?!#)|(?:https?|file|data):", content):
                    failures.append(error(base + ".changes.generated_svg.content", "generated SVG contains forbidden active, text, or external content"))
                if generated["contains_text"] and (not generated["text_editability_exempt"] or not generated.get("exemption_reason")):
                    failures.append(error(base + ".changes.generated_svg", "text-bearing generated SVG requires an exemption"))
    elif kind == "qa_report":
        metrics = document["metrics"]
        if metrics["editable_text_status"] == "not_applicable" and metrics["editable_text_ratio"] is not None:
            failures.append(error("$.metrics.editable_text_ratio", "must be null when status is not_applicable"))
        if metrics["editable_text_status"] == "applicable" and metrics["editable_text_ratio"] is None:
            failures.append(error("$.metrics.editable_text_ratio", "must be numeric when status is applicable"))
        if document["status"] == "pass" and document["hard_failures"]:
            failures.append(error("$.hard_failures", "must be empty when status is pass"))
        if document["status"] == "fail" and not document["hard_failures"]:
            failures.append(error("$.hard_failures", "must not be empty when status is fail"))
        if document["schema_version"] == "1.4":
            integrity = document.get("data_integrity")
            if integrity is None:
                failures.append(error("$.data_integrity", "qa report 1.4 requires data integrity evidence"))
            elif integrity["mismatch_count"] != sum(
                not all(item[field] is not False for field in ("native_type_match", "data_match", "merge_match", "header_style_match"))
                for item in integrity["objects"]
            ):
                failures.append(error("$.data_integrity.mismatch_count", "must equal failed data integrity objects"))
    elif kind == "font_audit":
        if document["font_violations"] != sum(len(item["violations"]) for item in document["runs"]):
            failures.append(error("$.font_violations", "must equal the total run violation count"))
        if (document["status"] == "pass") != (document["font_violations"] == 0):
            failures.append(error("$.status", "must match font_violations"))
    elif kind == "render_report":
        if document["attempts"][-1]["status"] != "passed":
            failures.append(error("$.attempts", "final render attempt must pass"))
        if document["attempts"][-1]["renderer"] != document["renderer"]:
            failures.append(error("$.renderer", "must match the successful attempt"))
        if document["fallback_used"] != (len(document["attempts"]) > 1):
            failures.append(error("$.fallback_used", "must reflect whether a fallback attempt was used"))
    elif kind == "run_state":
        if document["current_iteration"] > document["max_iterations"]:
            failures.append(error("$.current_iteration", "must not exceed max_iterations"))
        allowed = {
            "input_pending": {"planning", "failed"}, "planning": {"spec_ready", "failed"},
            "spec_ready": {"building", "failed"}, "building": {"structural_pass", "structural_fail", "failed"},
            "structural_fail": {"planning", "failed"}, "structural_pass": {"reviewing", "failed"},
            "reviewing": {"review_evaluating", "delivered_with_warnings", "failed"},
            "review_evaluating": {"review_pass", "review_revise", "review_fail", "review_warning_candidate", "delivered_with_warnings", "failed"},
            "review_revise": {"planning", "failed"}, "review_pass": {"packaging", "failed"},
            "review_fail": {"failed"}, "review_warning_candidate": {"awaiting_user_acceptance", "failed"},
            "awaiting_user_acceptance": {"packaging", "failed"}, "packaging": {"delivered", "failed"},
            "delivered": set(), "delivered_with_warnings": set(), "failed": set(),
        }
        for index, item in enumerate(document["history"]):
            if item["to"] not in allowed[item["from"]]:
                failures.append(error(f"$.history[{index}]", "history contains a forbidden transition"))
            if (item["artifact"] is None) != (item["artifact_sha256"] is None):
                failures.append(error(f"$.history[{index}]", "artifact and artifact_sha256 must both be null or both be present"))
            if item["artifact"] is not None and not is_safe_relative_path(item["artifact"]):
                failures.append(error(f"$.history[{index}].artifact", "must be a safe work-root-relative path"))
            if not _is_utc_timestamp(item["timestamp_utc"]):
                failures.append(error(f"$.history[{index}].timestamp_utc", "must be a valid UTC timestamp"))
            if index and document["history"][index - 1]["to"] != item["from"]:
                failures.append(error(f"$.history[{index}].from", "history transition chain is discontinuous"))
        if document["history"] and document["history"][-1]["to"] != document["state"]:
            failures.append(error("$.state", "must equal the final history transition target"))
        pending = document.get("pending_decision")
        if pending and pending["iteration"] != document["current_iteration"]:
            failures.append(error("$.pending_decision.iteration", "must match current_iteration"))
        acceptance = document.get("acceptance")
        if acceptance and pending and acceptance["warning_candidate_sha256"] != pending["review_evaluation_sha256"]:
            failures.append(error("$.acceptance.warning_candidate_sha256", "must match pending review evaluation"))
        if acceptance and not _is_utc_timestamp(acceptance["decision_at_utc"]):
            failures.append(error("$.acceptance.decision_at_utc", "must be a valid UTC timestamp"))
        delivery = document.get("delivery")
        if delivery and delivery["accepted_iteration"] != document["current_iteration"]:
            failures.append(error("$.delivery.accepted_iteration", "must match current_iteration"))
        if delivery:
            prefix = delivery["output_name"] + "_"
            expected_suffixes = {"editable.pptx", "assets.zip", "preview.png", "qa_report.json", "review_report.json", "review_evaluation.json", "delivery_decision.json"}
            if set(delivery["files"]) != {prefix + suffix for suffix in expected_suffixes}:
                failures.append(error("$.delivery.files", "must contain the exact seven delivery filenames"))
    elif kind == "build_summary":
        expected = document["expected_element_count"]
        built = document["built_element_count"]
        if expected != len(document["build_order"]):
            failures.append(error("$.build_order", "length must equal expected_element_count"))
        if expected != len(document["element_map"]):
            failures.append(error("$.element_map", "length must equal expected_element_count"))
        if built != expected or document["missing_element_ids"] or document["unexpected_element_ids"]:
            failures.append(error("$", "successful build summary requires complete element reconciliation"))
    elif kind == "agent_role":
        if set(document["model_policy"]["required_capabilities"]) != {"image-input", "structured-json"}:
            failures.append(error("$.model_policy.required_capabilities", "both image-input and structured-json are required"))
    elif kind == "agent_call_record":
        if document["status"] == "succeeded" and not document["context_id"]:
            failures.append(error("$.context_id", "successful calls require a context id"))
        if document["context_id"].strip().lower() in {"unknown", "unavailable", "not_exposed", "placeholder"}:
            failures.append(error("$.context_id", "context id cannot be an unavailable placeholder"))
        mode = document["model_selection_mode"]
        requested = document["requested_model"]
        if mode == "runtime-default" and requested is not None:
            failures.append(error("$.requested_model", "runtime-default calls cannot request a model"))
        if mode == "explicit" and requested is None:
            failures.append(error("$.requested_model", "explicit calls require a requested model"))
        if document["schema_version"] == "1.4":
            context = document["context_evidence"]
            if context["context_id"] != document["context_id"] or context["parent_context_id"] is not None:
                failures.append(error("$.context_evidence", "fresh context evidence must match the observed context and have no parent", "call_record"))
    elif kind == "review_evaluation":
        dimensions = [item["dimension"] for item in document["score_adjustments"]]
        if len(dimensions) != len(set(dimensions)):
            failures.append(error("$.score_adjustments", "score adjustment dimensions must be unique"))
        if document["policy_decision"] == "pass" and document["failed_visual_checks"]:
            failures.append(error("$.policy_decision", "pass is forbidden while a mandatory visual check fails"))
    elif kind == "delivery_decision":
        status = document["status"]
        if not _is_utc_timestamp(document["timestamp_utc"]):
            failures.append(error("$.timestamp_utc", "must be a valid UTC timestamp"))
        for field in ("approval", "rejection"):
            if field in document and not _is_utc_timestamp(document[field]["decision_at_utc"]):
                failures.append(error(f"$.{field}.decision_at_utc", "must be a valid UTC timestamp"))
        if status == "pass" and document["warnings"]:
            failures.append(error("$.warnings", "normal pass cannot include warnings"))
        if status == "pass_with_warnings" and document["approval"]["warning_candidate_sha256"] != document["review_evaluation_sha256"]:
            failures.append(error("$.approval.warning_candidate_sha256", "must match review_evaluation_sha256"))
    if failures:
        raise ContractError(failures)


def cross_validate(documents: dict[str, dict[str, Any]]) -> None:
    failures: list[dict[str, str]] = []
    manifest_ids = {item["id"] for item in documents.get("asset_manifest", {}).get("assets", [])}
    if "crops" in documents and "asset_manifest" in documents:
        for index, item in enumerate(documents["crops"]["assets"]):
            if item["id"] not in manifest_ids:
                failures.append(error(f"$.crops.assets[{index}].id", "crop asset is missing from asset manifest"))
    if "layout" in documents and "asset_manifest" in documents:
        manifest_by_id = {item["id"]: item for item in documents["asset_manifest"]["assets"]}
        for index, item in enumerate(documents["layout"]["elements"]):
            if item.get("asset_id") and item["asset_id"] not in manifest_ids:
                failures.append(error(f"$.layout.elements[{index}].asset_id", "unknown asset reference"))
            elif item.get("asset_id"):
                asset = manifest_by_id[item["asset_id"]]
                if item.get("contains_text", asset["contains_text"]) != asset["contains_text"]:
                    failures.append(error(f"$.layout.elements[{index}].contains_text", "must match asset manifest"))
                if item.get("text_editability_exempt", asset["text_editability_exempt"]) != asset["text_editability_exempt"]:
                    failures.append(error(f"$.layout.elements[{index}].text_editability_exempt", "must match asset manifest"))
    if "request" in documents and "layout" in documents:
        if documents["request"]["topic"] != documents["layout"]["metadata"]["topic"]:
            failures.append(error("$.layout.metadata.topic", "must match request topic"))
    if failures:
        raise ContractError(failures)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_build_ready(manifest_path: Path, document: dict[str, Any]) -> None:
    failures: list[dict[str, str]] = []
    base = manifest_path.parent.resolve()
    for index, item in enumerate(document["assets"]):
        path = (base / PurePosixPath(item["path"])).resolve()
        try:
            path.relative_to(base)
        except ValueError:
            failures.append(error(f"$.assets[{index}].path", "asset escapes manifest directory"))
            continue
        required = ("width_px", "height_px", "size_bytes", "sha256")
        for field in required:
            if field not in item:
                failures.append(error(f"$.assets[{index}].{field}", "required for build-ready"))
        if not path.is_file():
            failures.append(error(f"$.assets[{index}].path", "asset file does not exist"))
            continue
        if path.is_symlink():
            failures.append(error(f"$.assets[{index}].path", "symbolic links are not allowed"))
        if item.get("size_bytes") != path.stat().st_size:
            failures.append(error(f"$.assets[{index}].size_bytes", "does not match file size"))
        if item.get("sha256", "").lower() != sha256_file(path):
            failures.append(error(f"$.assets[{index}].sha256", "does not match file hash"))
        if item["security_status"] != "passed":
            failures.append(error(f"$.assets[{index}].security_status", "must be passed for build-ready"))
    if failures:
        raise ContractError(failures)
