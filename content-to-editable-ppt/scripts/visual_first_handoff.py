from __future__ import annotations

import copy
from typing import Any, TypedDict

from schema_utils import ContractError, error


class HandoffProjection(TypedDict):
    source_content: dict[str, Any]
    reconstruction_handoff: dict[str, Any]


def _slides_by_id(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {slide["slide_id"]: slide for slide in document["slides"]}


def validate_cross_stage(
    stage1_authority: dict[str, Any],
    stage2_handoff: dict[str, Any],
    stage1_authority_sha256: str,
) -> None:
    """Validate invariants that require both approved artifacts.

    File existence, file hashes, and path containment belong to the filesystem
    adapter. This module only validates document identity and cross references.
    """

    failures: list[dict[str, str]] = []
    if stage1_authority["deck_id"] != stage2_handoff["deck_id"]:
        failures.append(error("$.deck_id", "Stage 1 and Stage 2 deck IDs do not match", "deck_id_mismatch"))
    if stage2_handoff["stage1_authority_sha256"] != stage1_authority_sha256:
        failures.append(error(
            "$.stage1_authority_sha256",
            "Stage 2 is not bound to the current Stage 1 Authority file",
            "stage1_authority_stale",
        ))

    stage1_ids = [slide["slide_id"] for slide in stage1_authority["slides"]]
    stage2_ids = [slide["slide_id"] for slide in stage2_handoff["slides"]]
    if len(stage1_ids) != len(set(stage1_ids)) or len(stage2_ids) != len(set(stage2_ids)) or set(stage1_ids) != set(stage2_ids):
        failures.append(error("$.slides", "Stage 1 and Stage 2 slide sets must match exactly", "slide_set_mismatch"))

    stage1_slides = _slides_by_id(stage1_authority)
    stage2_slides = _slides_by_id(stage2_handoff)
    for slide_id in sorted(set(stage1_slides) & set(stage2_slides)):
        stage1_slide = stage1_slides[slide_id]
        stage2_slide = stage2_slides[slide_id]
        authority_ids = {item["id"] for item in stage1_slide["objects"]}
        visual_ids = {item["id"] for item in stage2_slide["visual_objects"]}
        collision = sorted(authority_ids & visual_ids)
        if collision:
            failures.append(error(
                f"$.slides[{slide_id}].visual_objects",
                f"Stage 1 and Stage 2 object IDs collide: {', '.join(collision)}",
                "object_id_collision",
            ))

        allowed_overlap_ids = authority_ids | visual_ids
        for object_index, item in enumerate(stage2_slide["visual_objects"]):
            for overlap_index, overlap_id in enumerate(item["overlaps_with"]):
                path = f"$.slides[{slide_id}].visual_objects[{object_index}].overlaps_with[{overlap_index}]"
                if overlap_id == item["id"]:
                    failures.append(error(path, "visual object cannot overlap itself", "self_reference"))
                elif overlap_id not in allowed_overlap_ids:
                    failures.append(error(path, f"unknown overlap reference: {overlap_id}", "unknown_reference"))

    if failures:
        raise ContractError(failures)


def project_slide(
    stage1_authority: dict[str, Any],
    stage2_handoff: dict[str, Any],
    *,
    slide_id: str,
    source_image: str,
    provenance: dict[str, str],
) -> HandoffProjection:
    """Project one validated deck handoff into P1 and P3-facing artifacts."""

    stage1_slides = _slides_by_id(stage1_authority)
    stage2_slides = _slides_by_id(stage2_handoff)
    if slide_id not in stage1_slides or slide_id not in stage2_slides:
        raise ContractError([error("$.slide_id", f"unknown slide_id: {slide_id}", "unknown_slide")])

    stage1_slide = stage1_slides[slide_id]
    stage2_slide = stage2_slides[slide_id]
    source_content = {
        "text_items": [
            {"id": item["id"], "text": item["text"]}
            for item in stage1_slide["text_items"]
        ]
    }
    structure = stage1_slide["semantic_structure"]
    reconstruction_handoff = {
        "schema_version": "1.0",
        "deck_id": stage1_authority["deck_id"],
        "slide_id": slide_id,
        "order": stage1_slide["order"],
        "provenance": copy.deepcopy(provenance),
        "page": {
            "section": stage1_slide["section"],
            "role": stage1_slide["role"],
            "key_message": stage1_slide["key_message"],
            "source_refs": copy.deepcopy(stage1_slide["source_refs"]),
            "visual_need": stage1_slide["visual_need"],
            "wireframe": "wireframe.md",
        },
        "content": {"text_items": copy.deepcopy(stage1_slide["text_items"])},
        "semantic_structure": {
            "objects": copy.deepcopy(stage1_slide["objects"]),
            "regions": copy.deepcopy(structure["regions"]),
            "reading_order": copy.deepcopy(structure["reading_order"]),
            "relations": copy.deepcopy(structure["relations"]),
        },
        "structured_data": copy.deepcopy(stage1_slide["structured_data"]),
        "stage2": {
            "approved_design": source_image,
            "visual_spec": "visual-spec.json",
            "visual_objects": copy.deepcopy(stage2_slide["visual_objects"]),
        },
    }
    return {
        "source_content": source_content,
        "reconstruction_handoff": reconstruction_handoff,
    }
