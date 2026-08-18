from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any

from canonical_artifact import canonical_sha256
from reconstruction_authority import SCHEMA_DIR
from schema_utils import ContractError, error, validate_schema


ORDER_BINDINGS = {"slide_ordinal", "section_ordinal", "progress_fraction", "total_slide_count", "previous_slide_id", "next_slide_id"}
NATIVE_CLASSES = {"native_text", "native_shape", "native_chart"}
ASSET_CLASSES = {"sanitized_svg", "reusable_raster", "generated_foreground"}


def _issue(slide_id: str, index: int, code: str, path: str, message: str, classification: str = "blocking") -> dict[str, str]:
    seed = f"{slide_id}|{index}|{code}|{path}|{message}"
    issue_id = "P4-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12].upper()
    return {"validation_issue_id": issue_id, "code": code, "path": path, "message": message, "classification": classification}


def page_input_identity(seed_view: dict[str, Any], *, order_sensitive: bool, order_bindings: list[str], order_context: dict[str, Any]) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "deck_id": seed_view["deck_id"],
        "slide_id": seed_view["slide_id"],
        "output_ratio": seed_view["output_ratio"],
        "approved_preview_sha256": seed_view["approved_preview_sha256"],
        "element_map_sha256": seed_view["element_map_sha256"],
        "reconstruction_seed_view_sha256": canonical_sha256(seed_view),
        "content_authority_sha256": seed_view["content_authority_sha256"],
        "asset_manifest_sha256": seed_view["asset_manifest_sha256"],
        "visual_system_sha256": seed_view["visual_system_sha256"],
        "text_footprint_manifest_sha256": seed_view["text_footprint_manifest_sha256"],
    }
    if order_sensitive:
        identity["order_bindings"] = {key: order_context[key] for key in sorted(order_bindings)}
    return identity


def compile_reconstruction_spec(
    seed_view: dict[str, Any], *, order: int, order_sensitive: bool = False,
    order_bindings: list[str] | None = None, order_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_schema("reconstruction_seed_view", seed_view, SCHEMA_DIR)
    bindings = sorted(set(order_bindings or []))
    context = deepcopy(order_context or {})
    failures: list[dict[str, str]] = []
    unknown = set(bindings) - ORDER_BINDINGS
    if unknown:
        failures.append(error("$.order_bindings", f"unknown order bindings: {sorted(unknown)}", "invalid_order_binding"))
    if order_sensitive and not bindings:
        failures.append(error("$.order_bindings", "order-sensitive page requires at least one binding", "invalid_order_binding"))
    if not order_sensitive and (bindings or context):
        failures.append(error("$.order_bindings", "order-insensitive page cannot carry order context", "invalid_order_binding"))
    missing = [key for key in bindings if key not in context]
    extra = sorted(set(context) - set(bindings))
    if missing or extra:
        failures.append(error("$.order_context", f"context mismatch; missing={missing}, extra={extra}", "invalid_order_binding"))
    if order < 1:
        failures.append(error("$.order", "order must be positive", "invalid_order"))
    if failures:
        raise ContractError(failures)
    elements = [{"element_id": item["element_id"], "source_ref": item.get("source_ref"), "reconstruction_class": item["reconstruction_class"], "p4_strategy": item["p4_strategy"], "fidelity_priority": item["fidelity_priority"], "normalized_bbox": deepcopy(item["normalized_bbox"]), "z_index": item["z_index"], "implementation": deepcopy(item["implementation"])} for item in sorted(seed_view["seeds"], key=lambda seed: (seed["z_index"], seed["element_id"]))]
    identity = page_input_identity(seed_view, order_sensitive=order_sensitive, order_bindings=bindings, order_context=context)
    spec = {"schema_version":"1.0","artifact_type":"visual_reconstruction_spec","deck_id":seed_view["deck_id"],"slide_id":seed_view["slide_id"],"output_ratio":seed_view["output_ratio"],"order":order,"order_sensitive":order_sensitive,"order_bindings":bindings,"order_context":context,"approved_preview_sha256":seed_view["approved_preview_sha256"],"element_map_sha256":seed_view["element_map_sha256"],"reconstruction_seed_view_sha256":canonical_sha256(seed_view),"content_authority_sha256":seed_view["content_authority_sha256"],"asset_manifest_sha256":seed_view["asset_manifest_sha256"],"page_input_sha256":canonical_sha256(identity),"elements":elements,"status":"validated"}
    validate_schema("visual_reconstruction_spec", spec, SCHEMA_DIR)
    report = validate_reconstruction_spec(spec, seed_view)
    if report["status"] != "pass":
        raise ContractError([error(item["path"], item["message"], item["code"]) for item in report["issues"]])
    return spec


def validate_reconstruction_spec(spec: dict[str, Any], seed_view: dict[str, Any], *, allow_targeted_changes: bool = False) -> dict[str, Any]:
    validate_schema("visual_reconstruction_spec", spec, SCHEMA_DIR)
    validate_schema("reconstruction_seed_view", seed_view, SCHEMA_DIR)
    issues: list[dict[str, str]] = []
    slide_id = spec["slide_id"]
    for path, left, right in (
        ("$.deck_id", spec["deck_id"], seed_view["deck_id"]), ("$.slide_id", slide_id, seed_view["slide_id"]),
        ("$.output_ratio", spec["output_ratio"], seed_view["output_ratio"]),
        ("$.approved_preview_sha256", spec["approved_preview_sha256"], seed_view["approved_preview_sha256"]),
        ("$.element_map_sha256", spec["element_map_sha256"], seed_view["element_map_sha256"]),
        ("$.reconstruction_seed_view_sha256", spec["reconstruction_seed_view_sha256"], canonical_sha256(seed_view)),
        ("$.content_authority_sha256", spec["content_authority_sha256"], seed_view["content_authority_sha256"]),
        ("$.asset_manifest_sha256", spec["asset_manifest_sha256"], seed_view["asset_manifest_sha256"]),
    ):
        if left != right:
            issues.append(_issue(slide_id, len(issues), "authority_hash_mismatch", path, "spec no longer binds current reconstruction authority"))
    expected_input = canonical_sha256(page_input_identity(seed_view, order_sensitive=spec["order_sensitive"], order_bindings=spec["order_bindings"], order_context=spec["order_context"]))
    if spec["page_input_sha256"] != expected_input:
        issues.append(_issue(slide_id, len(issues), "page_identity_mismatch", "$.page_input_sha256", "page cache identity is not reproducible"))
    if spec["order_sensitive"] != bool(spec["order_bindings"]):
        issues.append(_issue(slide_id, len(issues), "invalid_order_binding", "$.order_bindings", "order-sensitive flag and bindings disagree"))
    if set(spec["order_context"]) != set(spec["order_bindings"]):
        issues.append(_issue(slide_id, len(issues), "invalid_order_binding", "$.order_context", "order context does not match declared bindings"))

    expected = {item["element_id"]: item for item in seed_view["seeds"]}
    actual = {item["element_id"]: item for item in spec["elements"]}
    if len(actual) != len(spec["elements"]):
        issues.append(_issue(slide_id, len(issues), "duplicate_element", "$.elements", "element ids must be unique"))
    missing = sorted(set(expected) - set(actual)); unknown = sorted(set(actual) - set(expected))
    if missing:
        issues.append(_issue(slide_id, len(issues), "missing_element", "$.elements", f"missing elements: {missing}"))
    if unknown:
        issues.append(_issue(slide_id, len(issues), "unknown_element", "$.elements", f"unknown elements: {unknown}"))
    for index, item in enumerate(spec["elements"]):
        base = f"$.elements[{index}]"; seed = expected.get(item["element_id"])
        bbox = item["normalized_bbox"]
        if bbox["x"] + bbox["w"] > 10000 or bbox["y"] + bbox["h"] > 10000:
            issues.append(_issue(slide_id, index, "bbox_out_of_bounds", base + ".normalized_bbox", "element exceeds slide bounds", "correctable"))
        if seed is None:
            continue
        for field in ("source_ref", "reconstruction_class", "p4_strategy", "fidelity_priority"):
            if item.get(field) != seed.get(field):
                issues.append(_issue(slide_id, index, "reconstruction_authority_drift", base + "." + field, f"{field} differs from frozen seed"))
        if item["normalized_bbox"] != seed["normalized_bbox"] and not allow_targeted_changes:
            issues.append(_issue(slide_id, index, "unbound_geometry_change", base + ".normalized_bbox", "initial spec geometry must equal seed", "correctable"))
        if item["z_index"] != seed["z_index"] and not allow_targeted_changes:
            issues.append(_issue(slide_id, index, "unbound_geometry_change", base + ".z_index", "initial spec z-index must equal seed", "correctable"))
        if item["implementation"] != seed["implementation"] and not allow_targeted_changes:
            issues.append(_issue(slide_id, index, "reconstruction_seed_drift", base + ".implementation", "initial implementation must be a deterministic seed projection"))
        impl = item["implementation"]; kind = item["reconstruction_class"]
        if kind == "native_text":
            required = {"content_ref", "text", "text_sha256", "font_family", "minimum_font_size_pt", "font_size_pt", "margin_milli", "line_spacing_milli", "wrap_policy", "color"}
            if not required.issubset(impl) or hashlib.sha256(impl.get("text", "").encode("utf-8")).hexdigest() != impl.get("text_sha256"):
                issues.append(_issue(slide_id, index, "native_text_seed_incomplete", base + ".implementation", "native text implementation is incomplete"))
        elif kind == "native_shape":
            if "shape_kind" not in impl or not {"fill_color", "border_color", "corner_radius", "shadow_token", "opacity_milli"}.issubset(impl.get("style_seed", {})):
                issues.append(_issue(slide_id, index, "native_shape_seed_incomplete", base + ".implementation", "native shape implementation is incomplete"))
        elif kind == "native_chart":
            if "chart_spec" not in impl or canonical_sha256(impl.get("chart_spec", {})) != impl.get("chart_spec_sha256"):
                issues.append(_issue(slide_id, index, "chart_seed_incomplete", base + ".implementation", "chart implementation is incomplete"))
        elif kind in ASSET_CLASSES:
            if not {"asset_ref", "approved_record_sha256", "actual_asset_sha256", "asset_path", "fit"}.issubset(impl):
                issues.append(_issue(slide_id, index, "asset_seed_incomplete", base + ".implementation", "asset implementation is incomplete"))
            if bbox == {"x": 0, "y": 0, "w": 10000, "h": 10000}:
                issues.append(_issue(slide_id, index, "full_slide_raster_substitution", base + ".normalized_bbox", "content asset cannot substitute the entire slide"))
        elif kind == "generated_background":
            if impl.get("background_strategy") not in {"reconstructable_background", "approved_background_raster"}:
                issues.append(_issue(slide_id, index, "background_seed_incomplete", base + ".implementation", "background strategy is not frozen"))
        if item["fidelity_priority"] in {"critical", "major"} and not impl:
            issues.append(_issue(slide_id, index, "reconstruction_seed_incomplete", base + ".implementation", "Critical/Major element has no implementation"))
    blocking = [item for item in issues if item["classification"] == "blocking"]
    correctable = [item for item in issues if item["classification"] == "correctable"]
    status = "blocking" if blocking else "targeted_patch_required" if correctable else "pass"
    report = {"schema_version":"1.0","artifact_type":"reconstruction_validation_report","deck_id":spec["deck_id"],"slide_id":slide_id,"spec_sha256":canonical_sha256(spec),"status":status,"issues":issues}
    validate_schema("reconstruction_validation_report", report, SCHEMA_DIR)
    return report
