from __future__ import annotations

from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, validate_schema


def _raise(failures: list[dict[str, str]]) -> None:
    if failures:
        raise ContractError(failures)


def validate_task_route(document: dict[str, Any], schema_dir: Path) -> None:
    validate_schema("task_route", document, schema_dir)
    failures: list[dict[str, str]] = []
    revision = document["revision"]
    parent = document["parent_route_sha256"]
    if revision == 1 and parent is not None:
        failures.append(error("$.parent_route_sha256", "revision 1 route must not have a parent"))
    if revision > 1 and parent is None:
        failures.append(error("$.parent_route_sha256", "route revision requires the previous route hash"))
    _raise(failures)


def route_event(document: dict[str, Any]) -> str:
    return {
        "needs_clarification": "request_route_clarification",
        "image_to_editable_ppt": "route_image_to_ppt",
        "content_to_ppt": "route_content_to_ppt",
    }[document["route"]]


def material_evaluation(document: dict[str, Any]) -> dict[str, Any]:
    materials = document["materials"]
    authorizations = {item["material_id"]: item for item in document["ignore_authorizations"]}
    blockers: list[str] = []
    warnings: list[str] = []
    for material in materials:
        authorization = authorizations.get(material["material_id"])
        authorized = bool(authorization and authorization["material_record_sha256"] == canonical_sha256(material))
        unreadable = material["read_status"] != "readable"
        if material["required_for_task"] and unreadable and not authorized:
            blockers.append(material["material_id"])
        elif unreadable:
            warnings.append(material["material_id"])
    return {"blockers": blockers, "warnings": warnings, "ready": not blockers}


def validate_material_understanding(document: dict[str, Any], schema_dir: Path) -> dict[str, Any]:
    validate_schema("material_understanding", document, schema_dir)
    failures: list[dict[str, str]] = []
    materials = document["materials"]
    material_ids = [item["material_id"] for item in materials]
    if len(material_ids) != len(set(material_ids)):
        failures.append(error("$.materials", "material_id values must be unique"))
    material_by_id = {item["material_id"]: item for item in materials}
    authorization_ids: set[str] = set()
    for index, authorization in enumerate(document["ignore_authorizations"]):
        material_id = authorization["material_id"]
        if material_id in authorization_ids:
            failures.append(error(f"$.ignore_authorizations[{index}].material_id", "duplicate material authorization"))
        authorization_ids.add(material_id)
        material = material_by_id.get(material_id)
        if material is None:
            failures.append(error(f"$.ignore_authorizations[{index}].material_id", "authorization references an unknown material"))
        elif authorization["material_record_sha256"] != canonical_sha256(material):
            failures.append(error(f"$.ignore_authorizations[{index}].material_record_sha256", "authorization does not bind the current material failure record"))

    for index, material in enumerate(materials):
        readable = material["read_status"] == "readable"
        if readable and (material["content_sha256"] is None or material["reason"] is not None):
            failures.append(error(f"$.materials[{index}]", "readable material requires content_sha256 and no failure reason"))
        if not readable and not material["reason"]:
            failures.append(error(f"$.materials[{index}].reason", "non-readable material requires a reason"))

    fact_ids: set[str] = set()
    valid_sources = set(material_ids) | {"USER"}
    for index, fact in enumerate(document["facts"]):
        if fact["fact_id"] in fact_ids:
            failures.append(error(f"$.facts[{index}].fact_id", "duplicate fact_id"))
        fact_ids.add(fact["fact_id"])
        if fact["kind"] != "derived_transition" and not fact["source_refs"]:
            failures.append(error(f"$.facts[{index}].source_refs", "substantive content requires a source"))
        for source in fact["source_refs"]:
            if source not in valid_sources:
                failures.append(error(f"$.facts[{index}].source_refs", f"unknown or unauthorized source: {source}"))

    evaluation = material_evaluation(document)
    authorized_ids = set(authorization_ids)
    for index, material in enumerate(materials):
        expected = material["material_id"] in evaluation["blockers"]
        if material["blocking"] != expected:
            failures.append(error(f"$.materials[{index}].blocking", f"expected blocking={str(expected).lower()}"))
    expected_status = "ready" if evaluation["ready"] else "blocked"
    if document["status"] != expected_status:
        failures.append(error("$.status", f"expected {expected_status}"))
    for material_id in evaluation["warnings"]:
        if not any(material_id in warning for warning in document["warnings"]):
            failures.append(error("$.warnings", f"missing warning for non-blocking unreadable material {material_id}"))
    _raise(failures)
    return {**evaluation, "authorized_materials": sorted(authorized_ids)}
