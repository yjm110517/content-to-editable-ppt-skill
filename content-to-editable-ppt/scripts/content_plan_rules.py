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


def validate_candidate_outline(
    document: dict[str, Any],
    *,
    deck_request: dict[str, Any],
    materials: dict[str, Any],
    schema_dir: Path,
) -> None:
    validate_schema("candidate_outline", document, schema_dir)
    validate_schema("deck_request", deck_request, schema_dir)
    validate_material_understanding(materials, schema_dir)
    failures: list[dict[str, str]] = []
    if materials["status"] != "ready":
        failures.append(error("$.material_understanding_sha256", "candidate outline requires ready materials"))
    if document["deck_id"] != deck_request["deck_id"] or document["deck_id"] != materials["deck_id"]:
        failures.append(error("$.deck_id", "deck identity does not match request and materials"))
    if document["material_understanding_sha256"] != canonical_sha256(materials):
        failures.append(error("$.material_understanding_sha256", "candidate does not bind the current material understanding"))
    if len(document["pages"]) != deck_request["page_count"]:
        failures.append(error("$.pages", f"expected exactly {deck_request['page_count']} pages"))
    if document["revision"] == 1:
        if document["parent_sha256"] is not None or document["host_pass_counts"]["revision"] != 0:
            failures.append(error("$.revision", "initial candidate must have no parent and zero revision passes"))
    else:
        if document["parent_sha256"] is None or not document.get("user_revision_request_sha256"):
            failures.append(error("$.revision", "candidate revision requires parent and user request hashes"))
        if document["host_pass_counts"]["revision"] != document["revision"] - 1:
            failures.append(error("$.host_pass_counts.revision", "revision pass count must equal revision - 1"))

    facts = {fact["fact_id"] for fact in materials["facts"]}
    allowed_sources = facts | {"USER"}
    slide_ids: set[str] = set()
    content_refs: set[str] = set()
    for index, page in enumerate(document["pages"]):
        base = f"$.pages[{index}]"
        if page["order"] != index + 1:
            failures.append(error(base + ".order", "page order must be continuous and match array order"))
        if page["slide_id"] in slide_ids:
            failures.append(error(base + ".slide_id", "duplicate slide_id"))
        slide_ids.add(page["slide_id"])
        refs = [page["title"]["content_ref"], *[block["content_ref"] for block in page["content_blocks"]]]
        for ref in refs:
            if ref in content_refs:
                failures.append(error(base, f"duplicate content_ref: {ref}"))
            content_refs.add(ref)
        for block_index, block in enumerate(page["content_blocks"]):
            if block["order"] != block_index + 1:
                failures.append(error(f"{base}.content_blocks[{block_index}].order", "content block order must be continuous"))
            for source in block["source_refs"]:
                if source not in allowed_sources:
                    failures.append(error(f"{base}.content_blocks[{block_index}].source_refs", f"unknown source fact: {source}"))
        for source in page["source_refs"]:
            if source not in allowed_sources:
                failures.append(error(base + ".source_refs", f"unknown source fact: {source}"))
        for text_path, text in [(base + ".title.text", page["title"]["text"]), *[(f"{base}.content_blocks[{i}].text", item["text"]) for i, item in enumerate(page["content_blocks"])]]:
            if "\r" in text or text != __import__("unicodedata").normalize("NFC", text):
                failures.append(error(text_path, "confirmed text must already use NFC and LF line endings"))
    _raise(failures)


def validate_outline_confirmation(candidate: dict[str, Any], confirmation: dict[str, Any], schema_dir: Path) -> None:
    validate_schema("outline_confirmation", confirmation, schema_dir)
    failures: list[dict[str, str]] = []
    if confirmation["deck_id"] != candidate["deck_id"]:
        failures.append(error("$.deck_id", "confirmation deck does not match candidate"))
    if confirmation["candidate_revision"] != candidate["revision"]:
        failures.append(error("$.candidate_revision", "confirmation does not bind the candidate revision"))
    if confirmation["candidate_sha256"] != canonical_sha256(candidate):
        failures.append(error("$.candidate_sha256", "confirmation does not bind the candidate canonical hash"))
    _raise(failures)


def approved_outline_from(
    candidate: dict[str, Any],
    confirmation: dict[str, Any],
    *,
    revision: int,
    parent_sha256: str | None,
    approved_at_utc: str,
) -> dict[str, Any]:
    if confirmation["status"] != "confirmed":
        raise ContractError([error("$.status", "only a confirmed response can promote an outline")])
    return {
        "schema_version": "1.0",
        "canonicalization_version": "p1-rfc8785-nfc-1",
        "artifact_id": f"{candidate['deck_id']}-approved-outline-r{revision}",
        "deck_id": candidate["deck_id"],
        "revision": revision,
        "parent_sha256": parent_sha256,
        "candidate_revision": candidate["revision"],
        "candidate_sha256": canonical_sha256(candidate),
        "confirmation_id": confirmation["confirmation_id"],
        "confirmation_sha256": canonical_sha256(confirmation),
        "pages": __import__("copy").deepcopy(candidate["pages"]),
        "approved_at_utc": approved_at_utc,
    }
