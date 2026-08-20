from __future__ import annotations

import mimetypes
import re
import hashlib
import math
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import rfc8785
from schema_utils import ContractError, error, validate_schema


P5_INPUT_PURPOSES = {
    "approved-preview-contact-sheet.png": "approved_preview_contact_sheet",
    "final-candidate-contact-sheet.png": "final_candidate_contact_sheet",
    "approved-vs-final-comparison-sheet.png": "approved_vs_final_comparison_sheet",
    "deck-visual-system-summary.json": "deck_visual_system_summary",
    "deck-final-qa-report.json": "deck_final_qa_report",
    "powerpoint-roundtrip-report.json": "powerpoint_roundtrip_report",
    "p4-fidelity-inheritance.json": "p4_fidelity_inheritance",
    "exception-review-hashes.json": "exception_review_hashes",
    "deck-consistency-reviewer-response.schema.json": "response_schema",
    "exception-review-evidence.json": "exception_review_evidence",
    "exception-contact-sheets.png": "exception_contact_sheets",
    "exception-reviewer-response.schema.json": "response_schema",
}


def _normalize_for_request(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite numbers are forbidden in reviewer request evidence")
        return value
    if isinstance(value, list):
        return [_normalize_for_request(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("reviewer request evidence keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in result:
                raise ValueError("duplicate reviewer request evidence key after NFC normalization")
            result[normalized_key] = _normalize_for_request(item)
        return result
    raise ValueError(f"unsupported reviewer request evidence value: {type(value).__name__}")


def request_evidence_sha256(value: Any) -> str:
    return hashlib.sha256(rfc8785.dumps(_normalize_for_request(value))).hexdigest()


def input_media_type(name: str) -> str:
    if name.endswith(".schema.json"):
        return "application/schema+json"
    if name.endswith(".json"):
        return "application/json"
    if name.endswith(".md"):
        return "text/markdown"
    guessed, _ = mimetypes.guess_type(name)
    return guessed or "application/octet-stream"


def input_purpose(name: str) -> str:
    if name in P5_INPUT_PURPOSES:
        return P5_INPUT_PURPOSES[name]
    return re.sub(r"[^a-z0-9]+", "_", Path(name).stem.lower()).strip("_") or "agent_input"


def input_manifest_entry(name: str, digest: str) -> dict[str, str]:
    return {
        "name": name,
        "filename": name,
        "sha256": digest,
        "media_type": input_media_type(name),
        "purpose": input_purpose(name),
    }


def validate_input_manifest(manifest: dict[str, Any], expected_names: list[str]) -> None:
    failures: list[dict[str, str]] = []
    entries = manifest.get("inputs")
    if not isinstance(entries, list):
        raise ContractError([error("$.inputs", "call manifest inputs must be an ordered array", "call_record")])
    actual_names = [item.get("name") for item in entries if isinstance(item, dict)]
    if actual_names != expected_names:
        failures.append(error("$.inputs", "ordered input profile does not match the selected role profile", "input_allowlist"))
    for index, item in enumerate(entries):
        base = f"$.inputs[{index}]"
        if not isinstance(item, dict):
            failures.append(error(base, "input manifest entry must be an object", "call_record"))
            continue
        name = item.get("name")
        if not isinstance(name, str) or item.get("filename") != name:
            failures.append(error(base, "input name and filename must be the same safe profile name", "call_record"))
            continue
        if item.get("media_type") != input_media_type(name):
            failures.append(error(base + ".media_type", "input media type does not match the profile contract", "call_record"))
        if item.get("purpose") != input_purpose(name):
            failures.append(error(base + ".purpose", "input purpose does not match the profile contract", "call_record"))
        digest = item.get("sha256")
        if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
            failures.append(error(base + ".sha256", "input SHA-256 is invalid", "call_record"))
    if failures:
        raise ContractError(failures)


def validate_model_identity(identity: dict[str, Any], *, expected_parameters: dict[str, Any]) -> str:
    validate_schema("reviewer_model_identity", identity, Path(__file__).resolve().parents[1] / "schemas")
    if identity.get("parameters") != expected_parameters:
        raise ContractError([error("$.resolved_model_identity.parameters", "resolved model parameters differ from the call manifest", "call_record")])
    return request_evidence_sha256(identity)


def transport_request_sha256(*, call_manifest_sha256: str, manifest: dict[str, Any], model_identity_sha256: str) -> str:
    return request_evidence_sha256({
        "call_manifest_sha256": call_manifest_sha256,
        "ordered_inputs": manifest["inputs"],
        "system_prompt_sha256": manifest["prompt_sha256"],
        "response_schema_sha256": manifest["output_schema_sha256"],
        "resolved_model_identity_sha256": model_identity_sha256,
        "parameters": manifest["parameters"],
    })


def validate_runtime_timestamps(record: dict[str, Any]) -> None:
    fields = ("prepared_at_utc", "invoked_at_utc", "completed_at_utc")
    values: list[datetime] = []
    failures: list[dict[str, str]] = []
    for field in fields:
        value = record.get(field)
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) and value.endswith("Z") else None
        except ValueError:
            parsed = None
        if parsed is None or parsed.utcoffset() is None:
            failures.append(error(f"$.{field}", "runtime timestamp must be an ISO-8601 UTC value ending in Z", "call_record"))
        else:
            values.append(parsed)
    if len(values) == 3 and values != sorted(values):
        failures.append(error("$.runtime_timestamps", "runtime timestamps are not monotonic", "call_record"))
    if failures:
        raise ContractError(failures)
