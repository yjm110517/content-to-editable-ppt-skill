from __future__ import annotations

import copy
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, is_safe_relative_path, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
CORRECTABLE = "correctable_contract_error"
BLOCKING = "blocking_authority_error"
REDESIGN = "redesign_required"
WARNING = "preview_warning"
SEMANTIC_CORRECTION_CODES = {"unknown_semantic_ref", "missing_semantic_ref", "invalid_semantic_ref"}
FOCAL_CORRECTION_CODES = {"unknown_focal_region", "missing_focal_region", "invalid_focal_region"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def layout_constraints_payload(document: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(document[key]) for key in (
        "density", "preferred_region_structure", "required_visual_zones", "layout_direction",
        "reserved_areas", "cross_slide_structural_consistency",
    )}


def slide_content_payload(document: dict[str, Any]) -> dict[str, Any]:
    return {"slide_id": document["slide_id"], "title": copy.deepcopy(document["title"]), "content_blocks": copy.deepcopy(document["content_blocks"])}


def page_metadata_payload(page: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(page[key]) for key in ("slide_id", "role", "purpose", "key_message", "visual_intent", "source_refs")}


def wireframe_input_payload(*, slide_content: dict[str, Any], page: dict[str, Any], layout_requirements: dict[str, Any], output_ratio: str) -> dict[str, Any]:
    return {
        "slide_id": slide_content["slide_id"],
        "slide_content_payload_sha256": canonical_sha256(slide_content_payload(slide_content)),
        "page_metadata_sha256": canonical_sha256(page_metadata_payload(page)),
        "layout_constraints_sha256": canonical_sha256(layout_constraints_payload(layout_requirements)),
        "output_ratio": output_ratio,
    }


def expected_authority(*, approved_outline: dict[str, Any], slide_content: dict[str, Any], page: dict[str, Any], layout_requirements: dict[str, Any], output_ratio: str) -> dict[str, str]:
    payload = wireframe_input_payload(slide_content=slide_content, page=page, layout_requirements=layout_requirements, output_ratio=output_ratio)
    return {
        "approved_outline_sha256": canonical_sha256(approved_outline),
        "approved_slide_content_sha256": canonical_sha256(slide_content),
        "slide_content_payload_sha256": payload["slide_content_payload_sha256"],
        "layout_requirements_sha256": canonical_sha256(layout_requirements),
        "layout_constraints_sha256": payload["layout_constraints_sha256"],
        "page_metadata_sha256": payload["page_metadata_sha256"],
        "wireframe_input_sha256": canonical_sha256(payload),
    }


def load_authority_bundle(*, p1_state_path: Path, deck_request_path: Path, approved_outline_path: Path, slide_content_dir: Path, layout_requirements_path: Path) -> dict[str, Any]:
    p1_state = load_json(p1_state_path)
    deck_request = load_json(deck_request_path)
    approved = load_json(approved_outline_path)
    layout = load_json(layout_requirements_path)
    for kind, document in (("content_plan_state", p1_state), ("deck_request", deck_request), ("approved_outline", approved), ("wireframe_layout_requirements", layout)):
        validate_schema(kind, document, SCHEMA_DIR)
    failures: list[dict[str, str]] = []
    if p1_state["state"] != "p1_complete":
        failures.append(error("$.p1_state.state", "P2 requires p1_complete", "p1_not_complete"))
    outline_sha256 = canonical_sha256(approved)
    frozen_outline_sha256 = p1_state["current_artifacts"].get("approved_outline_sha256")
    if frozen_outline_sha256 is None:
        failures.append(error(
            "$.p1_state.current_artifacts.approved_outline_sha256",
            "p1_complete requires a frozen Approved Outline hash",
            "missing_authority",
        ))
    elif frozen_outline_sha256 != outline_sha256:
        failures.append(error(
            "$.p1_state.current_artifacts.approved_outline_sha256",
            "supplied Approved Outline does not match the hash frozen by P1 State",
            "authority_hash_mismatch",
        ))
    deck_id = deck_request["deck_id"]
    for label, document in (("p1_state", p1_state), ("approved_outline", approved), ("layout_requirements", layout)):
        if document["deck_id"] != deck_id:
            failures.append(error(f"$.{label}.deck_id", "Authority Bundle deck_id mismatch", "deck_mismatch"))
    if layout["deck_request_sha256"] != canonical_sha256(deck_request):
        failures.append(error("$.layout_requirements.deck_request_sha256", "does not bind Deck Request", "authority_hash_mismatch"))
    expected_constraints = canonical_sha256(layout_constraints_payload(layout))
    if layout["layout_constraints_sha256"] != expected_constraints:
        failures.append(error("$.layout_requirements.layout_constraints_sha256", "layout constraints hash is invalid", "authority_hash_mismatch"))
    projection_path = slide_content_dir / "projection-manifest.json"
    if not projection_path.is_file():
        failures.append(error("$.slide_content_manifest", "projection-manifest.json is missing", "missing_authority"))
        projection = None
    else:
        try:
            projection = load_json(projection_path)
        except (OSError, UnicodeError, json.JSONDecodeError, ContractError):
            failures.append(error("$.slide_content_manifest", "projection-manifest.json is unreadable", "missing_authority"))
            projection = None
    if projection is not None:
        frozen_manifest_sha256 = p1_state["current_artifacts"].get("slide_content_manifest_sha256")
        actual_manifest_sha256 = canonical_sha256(projection)
        if frozen_manifest_sha256 is None:
            failures.append(error(
                "$.p1_state.current_artifacts.slide_content_manifest_sha256",
                "p1_complete requires a frozen Projection Manifest hash",
                "missing_authority",
            ))
        elif frozen_manifest_sha256 != actual_manifest_sha256:
            failures.append(error(
                "$.p1_state.current_artifacts.slide_content_manifest_sha256",
                "supplied Projection Manifest does not match the hash frozen by P1 State",
                "authority_hash_mismatch",
            ))
        if projection.get("deck_id") != deck_id or projection.get("approved_outline_sha256") != outline_sha256:
            failures.append(error("$.slide_content_manifest", "Projection Manifest does not bind Approved Outline", "authority_hash_mismatch"))
    contents: dict[str, dict[str, Any]] = {}
    if projection:
        for index, item in enumerate(projection.get("slides", [])):
            relative = item.get("path", "")
            if not is_safe_relative_path(relative):
                failures.append(error(f"$.slide_content_manifest.slides[{index}].path", "unsafe slide content path", "unsafe_path"))
                continue
            path = slide_content_dir / relative
            if not path.is_file():
                failures.append(error(f"$.slide_content_manifest.slides[{index}].path", "slide content file is missing", "missing_authority"))
                continue
            content = load_json(path)
            validate_schema("approved_slide_content", content, SCHEMA_DIR)
            if canonical_sha256(content) != item.get("sha256"):
                failures.append(error(f"$.slide_content_manifest.slides[{index}].sha256", "slide content hash mismatch", "authority_hash_mismatch"))
            contents[content["slide_id"]] = content
    pages = {item["slide_id"]: item for item in approved["pages"]}
    if set(contents) != set(pages):
        failures.append(error("$.slide_content_manifest.slides", "Slide Content IDs must exactly match Approved Outline", "slide_set_mismatch"))
    for slide_id in set(contents) & set(pages):
        if contents[slide_id]["order"] != pages[slide_id]["order"]:
            failures.append(error(f"$.slide_content.{slide_id}.order", "Slide Content order does not match Approved Outline", "order_mismatch"))
    if deck_request["page_count"] != len(pages):
        failures.append(error("$.deck_request.page_count", "page_count does not match Approved Outline", "page_count_mismatch"))
    if failures:
        raise ContractError(failures)
    return {"p1_state": p1_state, "deck_request": deck_request, "approved_outline": approved, "layout_requirements": layout, "projection_manifest": projection, "slide_contents": contents, "pages": pages}


def _issue(issues: list[dict[str, Any]], *, slide_id: str | None, classification: str, code: str, path: str, message: str) -> None:
    issues.append({
        "issue_id": f"WFV-{len(issues) + 1:03d}", "slide_id": slide_id, "classification": classification,
        "code": code, "path": path, "message": message, "correctable": classification == CORRECTABLE,
    })


def _contains(parent: dict[str, int], child: dict[str, int]) -> bool:
    return parent["x"] <= child["x"] and parent["y"] <= child["y"] and parent["x"] + parent["w"] >= child["x"] + child["w"] and parent["y"] + parent["h"] >= child["y"] + child["h"]


def _intersects(left: dict[str, int], right: dict[str, int]) -> bool:
    return max(left["x"], right["x"]) < min(left["x"] + left["w"], right["x"] + right["w"]) and max(left["y"], right["y"]) < min(left["y"] + left["h"], right["y"] + right["h"])


def validate_spec(spec: dict[str, Any], *, approved_outline: dict[str, Any], slide_content: dict[str, Any], page: dict[str, Any], layout_requirements: dict[str, Any], output_ratio: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    slide_id = slide_content["slide_id"]
    try:
        validate_schema("wireframe_spec", spec, SCHEMA_DIR)
    except ContractError as exc:
        for item in exc.errors:
            _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="schema_contract_error", path=item["path"], message=item["message"])
        return issues
    if spec["deck_id"] != approved_outline["deck_id"] or spec["slide_id"] != slide_id:
        _issue(issues, slide_id=slide_id, classification=BLOCKING, code="authority_identity_mismatch", path="$.deck_id", message="Spec identity does not match Authority Bundle")
    authority = expected_authority(approved_outline=approved_outline, slide_content=slide_content, page=page, layout_requirements=layout_requirements, output_ratio=output_ratio)
    for field, expected in authority.items():
        if spec["authority"].get(field) != expected:
            _issue(issues, slide_id=slide_id, classification=BLOCKING, code="authority_hash_mismatch", path=f"$.authority.{field}", message=f"{field} does not match authoritative input")
    if spec["output_ratio"] != output_ratio:
        _issue(issues, slide_id=slide_id, classification=BLOCKING, code="output_ratio_mismatch", path="$.output_ratio", message="Spec output ratio does not match Deck Request")
    regions = spec["regions"]
    ids = [item["region_id"] for item in regions]
    if len(ids) != len(set(ids)):
        _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="duplicate_region_id", path="$.regions", message="Region IDs must be unique")
    by_id = {item["region_id"]: item for item in regions}
    if spec["focal_region_id"] not in by_id:
        _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="unknown_focal_region", path="$.focal_region_id", message="Focal Region does not exist")
    approved_refs = [slide_content["title"]["content_ref"], *[item["content_ref"] for item in slide_content["content_blocks"]]]
    placed = [ref for region in regions for ref in region["content_refs"]]
    placed_counts = Counter(placed)
    for ref in approved_refs:
        if placed_counts[ref] == 0:
            _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="missing_content_ref", path="$.regions", message=f"Approved Content Ref is not placed: {ref}")
        elif placed_counts[ref] > 1:
            _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="duplicate_content_ref", path="$.regions", message=f"Approved Content Ref is placed more than once: {ref}")
    for ref in placed:
        if ref not in approved_refs:
            _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="unknown_content_ref", path="$.regions", message=f"Unknown Content Ref: {ref}")
    title_ref = slide_content["title"]["content_ref"]
    title_regions = [item for item in regions if title_ref in item["content_refs"]]
    if len(title_regions) == 1 and title_regions[0]["role"] != "title":
        _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="title_wrong_region", path="$.regions", message="Title Content Ref must be placed in a title Region")
    for index, region in enumerate(regions):
        base = f"$.regions[{index}]"
        box = region["bbox"]
        if box["x"] + box["w"] > 10000 or box["y"] + box["h"] > 10000:
            _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="bbox_out_of_bounds", path=base + ".bbox", message="Region exceeds normalized page bounds")
        if region["content_refs"] and (box["w"] < 400 or box["h"] < 300):
            _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="region_unusable", path=base + ".bbox", message="Content Region is too small for a preview label")
        if region["role"] == "decoration" and (region["content_refs"] or region["semantic_source_refs"]):
            _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="decoration_has_authority_refs", path=base, message="Decoration cannot carry content or semantic references")
        for ref in region["semantic_source_refs"]:
            if ref not in approved_refs:
                _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="unknown_semantic_ref", path=base + ".semantic_source_refs", message=f"Unknown Semantic Source Ref: {ref}")
        parent_id = region["parent_region_id"]
        if parent_id is None:
            if region["hierarchy_level"] != 1:
                _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="invalid_hierarchy_level", path=base + ".hierarchy_level", message="Root Region hierarchy_level must be 1")
        elif parent_id not in by_id:
            _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="unknown_parent_region", path=base + ".parent_region_id", message="Parent Region does not exist")
        else:
            parent = by_id[parent_id]
            if region["hierarchy_level"] != parent["hierarchy_level"] + 1:
                _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="invalid_hierarchy_level", path=base + ".hierarchy_level", message="Child hierarchy_level must equal Parent + 1")
    for region in regions:
        seen: set[str] = set()
        current = region
        while current["parent_region_id"] is not None and current["parent_region_id"] in by_id:
            if current["region_id"] in seen:
                _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="parent_cycle", path="$.regions", message="Region parent graph contains a cycle")
                break
            seen.add(current["region_id"])
            current = by_id[current["parent_region_id"]]
    relationships = spec["relationships"]
    relationship_ids = [item["relationship_id"] for item in relationships]
    if len(relationship_ids) != len(set(relationship_ids)):
        _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="duplicate_relationship_id", path="$.relationships", message="Relationship IDs must be unique")
    overlay_pairs: set[frozenset[str]] = set()
    for index, relationship in enumerate(relationships):
        for field in ("from_region_id", "to_region_id"):
            if relationship[field] not in by_id:
                _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="unknown_relationship_endpoint", path=f"$.relationships[{index}].{field}", message="Relationship endpoint does not exist")
        if relationship["kind"] == "overlay":
            overlay_pairs.add(frozenset((relationship["from_region_id"], relationship["to_region_id"])))
    for region in regions:
        parent_id = region["parent_region_id"]
        if parent_id in by_id and not _contains(by_id[parent_id]["bbox"], region["bbox"]) and frozenset((parent_id, region["region_id"])) not in overlay_pairs:
            _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="child_outside_parent", path="$.regions", message=f"Child {region['region_id']} leaves Parent bounds without overlay")
    for left_index, left in enumerate(regions):
        for right in regions[left_index + 1:]:
            if not _intersects(left["bbox"], right["bbox"]):
                continue
            pair = frozenset((left["region_id"], right["region_id"]))
            parent_child = left["parent_region_id"] == right["region_id"] or right["parent_region_id"] == left["region_id"]
            same_group = left["overlap_group"] is not None and left["overlap_group"] == right["overlap_group"]
            explicit_overlay = pair in overlay_pairs
            if parent_child or same_group or explicit_overlay:
                continue
            decorations = [item for item in (left, right) if item["role"] == "decoration"]
            if decorations:
                decoration = decorations[0]
                other = right if decoration is left else left
                if decoration["z_index"] < other["z_index"]:
                    continue
                _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="foreground_decoration_requires_overlay", path="$.regions", message="Foreground Decoration overlap requires an overlay relationship")
            else:
                _issue(issues, slide_id=slide_id, classification=CORRECTABLE, code="disallowed_accidental_intersection", path="$.regions", message=f"Independent Regions intersect: {left['region_id']} and {right['region_id']}")
    for requirement in layout_requirements["required_visual_zones"]:
        if requirement["scope"] not in {"all", slide_id}:
            continue
        count = sum(item["role"] == requirement["role"] for item in regions)
        if count < requirement["minimum_count"]:
            _issue(issues, slide_id=slide_id, classification=REDESIGN, code="required_visual_zone_missing", path="$.regions", message=f"Required {requirement['role']} zone is missing")
    return issues


def candidate_manifest_digest(specs: Iterable[dict[str, Any]]) -> str:
    ordered = sorted(({"slide_id": item["slide_id"], "sha256": canonical_sha256(item)} for item in specs), key=lambda item: item["slide_id"])
    return canonical_sha256({"specs": ordered})


def validation_report(*, deck_id: str, candidate_sha256: str, issues: list[dict[str, Any]], report_id: str, validated_at_utc: str | None = None) -> dict[str, Any]:
    blocking = any(item["classification"] in {BLOCKING, REDESIGN} for item in issues)
    correctable = any(item["classification"] == CORRECTABLE for item in issues)
    status = "blocking" if blocking else "correctable" if correctable else "pass"
    result = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "report_id": report_id, "deck_id": deck_id, "candidate_manifest_sha256": candidate_sha256, "status": status, "issues": issues, "validated_at_utc": validated_at_utc or utc_now()}
    validate_schema("wireframe_validation_report", result, SCHEMA_DIR)
    return result


def _target(spec: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    if operation["target_type"] == "spec":
        if operation["target_id"] is not None:
            raise ContractError([error("$.operations.target_id", "Spec target_id must be null", "invalid_correction")])
        return spec
    collection = "regions" if operation["target_type"] == "region" else "relationships"
    id_field = "region_id" if collection == "regions" else "relationship_id"
    result = next((item for item in spec[collection] if item[id_field] == operation["target_id"]), None)
    if result is None:
        raise ContractError([error("$.operations.target_id", "Correction target does not exist", "invalid_correction")])
    return result


def apply_correction(*, specs: list[dict[str, Any]], report: dict[str, Any], correction: dict[str, Any]) -> list[dict[str, Any]]:
    validate_schema("wireframe_validation_report", report, SCHEMA_DIR)
    validate_schema("wireframe_correction_record", correction, SCHEMA_DIR)
    failures: list[dict[str, str]] = []
    if report["status"] != "correctable":
        failures.append(error("$.validation_report.status", "only a correctable report may be patched", "invalid_correction"))
    if correction["candidate_manifest_sha256"] != report["candidate_manifest_sha256"] or correction["candidate_manifest_sha256"] != candidate_manifest_digest(specs):
        failures.append(error("$.candidate_manifest_sha256", "Correction does not bind current Candidate", "stale_correction"))
    if correction["validation_report_sha256"] != canonical_sha256(report):
        failures.append(error("$.validation_report_sha256", "Correction does not bind Validation Report", "stale_correction"))
    issues = {item["issue_id"]: item for item in report["issues"]}
    updated = copy.deepcopy(specs)
    by_slide = {item["slide_id"]: item for item in updated}
    matrices = {
        "spec": {"focal_region_id"},
        "region": {"bbox", "content_refs", "semantic_source_refs", "parent_region_id", "hierarchy_level", "z_index", "overlap_group"},
        "relationship": {"from_region_id", "to_region_id", "direction"},
    }
    for index, operation in enumerate(correction["operations"]):
        base = f"$.operations[{index}]"
        issue = issues.get(operation["validation_issue_id"])
        if issue is None or not issue["correctable"] or issue["slide_id"] != operation["slide_id"]:
            failures.append(error(base + ".validation_issue_id", "Operation is not bound to a correctable issue", "invalid_correction"))
            continue
        if operation["field"] not in matrices[operation["target_type"]]:
            failures.append(error(base + ".field", "Field is not allowed for this target type", "invalid_correction"))
            continue
        if operation["field"] == "semantic_source_refs" and issue["code"] not in SEMANTIC_CORRECTION_CODES:
            failures.append(error(base + ".field", "Legal Semantic Sources cannot be changed by Contract Correction", "protected_semantics"))
            continue
        if operation["field"] == "focal_region_id" and issue["code"] not in FOCAL_CORRECTION_CODES:
            failures.append(error(base + ".field", "Legal Focal Region cannot be changed by Contract Correction", "protected_focal_region"))
            continue
        spec = by_slide.get(operation["slide_id"])
        if spec is None:
            failures.append(error(base + ".slide_id", "Correction slide does not exist", "invalid_correction"))
            continue
        try:
            target = _target(spec, operation)
        except ContractError as exc:
            failures.extend(exc.errors)
            continue
        if target.get(operation["field"]) != operation["before"]:
            failures.append(error(base + ".before", "Correction before value does not match Candidate", "stale_correction"))
            continue
        target[operation["field"]] = copy.deepcopy(operation["after"])
    if failures:
        raise ContractError(failures)
    for spec in updated:
        validate_schema("wireframe_spec", spec, SCHEMA_DIR)
    return updated


def build_manifest(*, approved_outline: dict[str, Any], specs: list[dict[str, Any]], layout_requirements: dict[str, Any], output_ratio: str, artifact_id: str, revision: int, parent_sha256: str | None = None, previous_manifest: dict[str, Any] | None = None, created_at_utc: str | None = None) -> dict[str, Any]:
    specs_by_id = {item["slide_id"]: item for item in specs}
    previous = {item["slide_id"]: item for item in previous_manifest["slides"]} if previous_manifest else {}
    slides = []
    for page in sorted(approved_outline["pages"], key=lambda item: item["order"]):
        spec = specs_by_id[page["slide_id"]]
        digest = canonical_sha256(spec)
        old = previous.get(page["slide_id"])
        reused = bool(old and old["wireframe_input_sha256"] == spec["authority"]["wireframe_input_sha256"])
        if reused and old["spec_sha256"] != digest:
            raise ContractError([error(f"$.slides.{page['slide_id']}", "unchanged page input must reuse the previous Spec", "unexpected_page_rebuild")])
        slides.append({
            "slide_id": page["slide_id"], "order": page["order"], "spec_path": f"specs/{page['slide_id']}-r{spec['revision']:03d}.json",
            "spec_sha256": digest, "wireframe_input_sha256": spec["authority"]["wireframe_input_sha256"],
            "svg_path": old["svg_path"] if reused else None, "svg_sha256": old["svg_sha256"] if reused else None,
            "build_status": "reused" if reused else "rebuilt",
        })
    result = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": artifact_id, "deck_id": approved_outline["deck_id"], "revision": revision, "parent_sha256": parent_sha256, "output_ratio": output_ratio, "layout_requirements_sha256": canonical_sha256(layout_requirements), "slides": slides, "created_at_utc": created_at_utc or utc_now()}
    validate_schema("wireframe_manifest", result, SCHEMA_DIR)
    return result
