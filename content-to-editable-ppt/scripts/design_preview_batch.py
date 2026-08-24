from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, validate_schema


SCHEMA_DIR = __import__("pathlib").Path(__file__).resolve().parents[1] / "schemas"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_map_evidence(package: Path, *, deck_id: str, slide_id: str, generated_layer_sha256: str, prompt_package_sha256: str) -> dict[str, Any]:
    root = package.resolve()
    expected = {"map-input-manifest.json", "inputs", "raw_response.json", "finalized-element-map.json", "call-record.json"}
    actual = {item.name for item in root.iterdir()} if root.is_dir() else set()
    if actual != expected:
        raise ContractError([error("$.evidence_package", "Map evidence package has missing or unexpected entries", "invalid_evidence_package")])
    manifest = json.loads((root / "map-input-manifest.json").read_text(encoding="utf-8"))
    record = json.loads((root / "call-record.json").read_text(encoding="utf-8"))
    raw = json.loads((root / "raw_response.json").read_text(encoding="utf-8"))
    finalized = json.loads((root / "finalized-element-map.json").read_text(encoding="utf-8"))
    validate_schema("design_element_map_input_manifest", manifest, SCHEMA_DIR)
    validate_schema("design_element_map_call_record", record, SCHEMA_DIR)
    validate_schema("design_element_map", finalized, SCHEMA_DIR)
    failures: list[dict[str, str]] = []
    for field, expected_value in {"deck_id": deck_id, "slide_id": slide_id, "generated_layer_sha256": generated_layer_sha256, "prompt_package_sha256": prompt_package_sha256}.items():
        if manifest.get(field) != expected_value or record.get(field) != expected_value:
            failures.append(error(f"$.{field}", "Map evidence does not bind the current page authority", "authority_hash_mismatch"))
    manifest_sha = canonical_sha256(manifest)
    if record["map_input_manifest_sha256"] != manifest_sha:
        failures.append(error("$.call_record.map_input_manifest_sha256", "Map call record does not bind input manifest", "authority_hash_mismatch"))
    for item in manifest["inputs"]:
        target = root / "inputs" / item["filename"]
        if not target.is_file() or sha256_file(target) != item["sha256"]:
            failures.append(error("$.inputs", f"Map input hash mismatch: {item['filename']}", "authority_hash_mismatch"))
    if record["raw_response_sha256"] != sha256_file(root / "raw_response.json"):
        failures.append(error("$.call_record.raw_response_sha256", "Raw response hash mismatch", "authority_hash_mismatch"))
    if finalized != raw:
        failures.append(error("$.finalized_element_map", "Finalized map differs from raw Host response", "map_rewrite_forbidden"))
    if record["finalized_element_map_sha256"] != canonical_sha256(finalized):
        failures.append(error("$.call_record.finalized_element_map_sha256", "Finalized Element Map hash mismatch", "authority_hash_mismatch"))
    if finalized["deck_id"] != deck_id or finalized["slide_id"] != slide_id or finalized["generated_layer_sha256"] != generated_layer_sha256 or finalized["prompt_package_sha256"] != prompt_package_sha256:
        failures.append(error("$.finalized_element_map", "Element Map identity does not bind page inputs", "authority_hash_mismatch"))
    if failures:
        raise ContractError(failures)
    return {"manifest": manifest, "record": record, "element_map": finalized, "manifest_sha256": manifest_sha}


def initial_state(*, deck_id: str, slides: list[dict[str, Any]], artifacts: dict[str, str], anchor_slide_id: str) -> dict[str, Any]:
    state = {
        "schema_version": "1.0", "artifact_type": "design_preview_batch_state", "deck_id": deck_id,
        "state": "anchor_approved",
        "budgets": {"initial_generation_per_slide": 1, "technical_retry_per_stage": 2, "map_pass_per_page": 1, "map_correction_per_page": 1},
        "counters": {"image_generation_calls": 0, "host_map_pass_count": 0, "map_correction_count": 0, "automatic_regeneration_count": 0, "planner_calls": 0, "reviewer_calls": 0},
        "current_artifacts": dict(artifacts),
        "pages": [{"slide_id": item["slide_id"], "order": item["order"], "status": "anchor_approved" if item["slide_id"] == anchor_slide_id else "generated", "generated_layer_record_sha256": None, "map_input_manifest_sha256": None, "map_call_record_sha256": None, "element_map_sha256": None, "compatibility_report_sha256": None, "final_preview_record_sha256": None, "error_code": None} for item in slides],
        "history": [{"event": "anchor_imported", "evidence": artifacts["style_anchor_record_sha256"]}],
    }
    validate_schema("design_preview_batch_state", state, SCHEMA_DIR)
    return state


def page(state: dict[str, Any], slide_id: str) -> dict[str, Any]:
    matches = [item for item in state["pages"] if item["slide_id"] == slide_id]
    if len(matches) != 1:
        raise ContractError([error("$.slide_id", "slide is not present exactly once in batch state", "unknown_slide")])
    return matches[0]


def update_page(state: dict[str, Any], slide_id: str, *, status: str, **hashes: str | None) -> dict[str, Any]:
    result = copy.deepcopy(state)
    target = page(result, slide_id)
    target["status"] = status
    for key, value in hashes.items():
        if key not in target:
            raise ContractError([error("$.pages", f"unknown page field: {key}", "invalid_state")])
        target[key] = value
    result["history"].append({"event": f"page_{status}", "slide_id": slide_id, "evidence": canonical_sha256({key: value for key, value in hashes.items()}) if hashes else None})
    validate_schema("design_preview_batch_state", result, SCHEMA_DIR)
    return result


def refresh_state(state: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(state)
    statuses = {item["status"] for item in result["pages"]}
    if "failed" in statuses:
        result["state"] = "failed"
    elif all(item["status"] in {"rendered", "anchor_approved"} for item in result["pages"]):
        result["state"] = "contact_sheet_ready"
    elif "map_package_ready" in statuses or "generated" in statuses:
        result["state"] = "map_evidence_required"
    elif "mapped" in statuses or "compatible" in statuses or "preview_built" in statuses:
        result["state"] = "building_previews"
    validate_schema("design_preview_batch_state", result, SCHEMA_DIR)
    return result
