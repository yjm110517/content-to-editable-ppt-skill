from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_common import canonical_yaml_hash, load_role, normalized_text_bytes, sha256_bytes
from agent_request_evidence import transport_request_sha256, validate_input_manifest, validate_model_identity, validate_runtime_timestamps
from asset_common import sha256_file
from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
BASE_ENTRIES = {"call_manifest.json", "runtime-call-record.json", "system_prompt.md", "inputs", "raw_response.json", "finalized_response.json", "call_record.json"}


def validate_p5_reviewer_evidence(package: Path, *, expected_profile: str = "deck_consistency", require_live: bool = True) -> dict[str, Any]:
    root = package.resolve()
    actual_entries = {item.name for item in root.iterdir()} if root.is_dir() else set()
    allowed_sets = (BASE_ENTRIES, BASE_ENTRIES | {"call-ledger.json"})
    if not root.is_dir() or actual_entries not in allowed_sets:
        raise ContractError([error("$.evidence_package", "P5 reviewer evidence file set is incomplete or unexpected", "invalid_evidence_package")])
    manifest = load_json(root / "call_manifest.json")
    runtime_record = load_json(root / "runtime-call-record.json")
    p5_record = load_json(root / "call_record.json")
    finalized = load_json(root / "finalized_response.json")
    validate_schema("agent_call_record", runtime_record, SCHEMA_DIR)
    validate_schema("p5_reviewer_call_record", p5_record, SCHEMA_DIR)
    if manifest.get("role") != "reviewer" or manifest.get("mode") != expected_profile or manifest.get("input_profile") != expected_profile:
        raise ContractError([error("$.call_manifest", "Reviewer evidence profile mismatch", "call_record")])
    config, config_path, prompt_path, output_schema = load_role("reviewer", SCHEMA_DIR, mode=expected_profile)
    validate_input_manifest(manifest, config["input_profiles"][expected_profile])
    failures: list[dict[str, str]] = []
    actual_inputs: dict[str, str] = {}
    for index, item in enumerate(manifest.get("inputs", [])):
        name, filename = item.get("name"), item.get("filename")
        if not isinstance(name, str) or not isinstance(filename, str) or Path(filename).name != filename:
            failures.append(error(f"$.call_manifest.inputs[{index}]", "invalid input identity", "call_record")); continue
        target = root / "inputs" / filename
        digest = sha256_file(target) if target.is_file() else ""
        if digest != item.get("sha256"):
            failures.append(error(f"$.call_manifest.inputs[{index}]", "frozen input hash mismatch", "authority_hash_mismatch"))
        actual_inputs[name] = digest
    expected_inputs = set(config["input_profiles"][expected_profile])
    if set(actual_inputs) != expected_inputs:
        failures.append(error("$.call_manifest.inputs", "input profile allowlist mismatch", "call_record"))
    manifest_sha = sha256_file(root / "call_manifest.json")
    evidence_sha = canonical_sha256({"call_manifest_sha256": manifest_sha, "inputs": {key: actual_inputs[key] for key in sorted(actual_inputs)}, "input_profile": expected_profile})
    comparisons = {
        "call_manifest_sha256": manifest_sha,
        "evidence_sha256": evidence_sha,
        "raw_response_sha256": sha256_file(root / "raw_response.json"),
        "finalized_response_sha256": sha256_file(root / "finalized_response.json"),
        "role_config_sha256": canonical_yaml_hash(config_path),
        "prompt_sha256": sha256_bytes(normalized_text_bytes(prompt_path)),
        "response_schema_sha256": sha256_file(output_schema),
        "context_id": runtime_record.get("context_id"),
        "parent_context_id": runtime_record.get("parent_context_id"),
    }
    for field, expected in comparisons.items():
        if p5_record.get(field) != expected:
            failures.append(error(f"$.call_record.{field}", "trusted reviewer binding mismatch", "authority_hash_mismatch"))
    if p5_record.get("input_profile") != expected_profile or p5_record.get("call_id") != manifest.get("call_id") or p5_record.get("deck_id") != manifest.get("task_id"):
        failures.append(error("$.call_record", "Reviewer evidence identity mismatch", "call_record"))
    if require_live and p5_record.get("live") is not True:
        failures.append(error("$.call_record.live", "ADR-040 requires a live Deck Consistency Review", "live_deck_review_required"))
    if p5_record.get("live") is True:
        if expected_profile == "deck_consistency" and finalized.get("schema_version") != "1.1":
            failures.append(error("$.finalized_response.schema_version", "Live Deck Consistency Review requires production schema 1.1", "live_deck_review_required"))
        identity = runtime_record.get("resolved_model_identity")
        try:
            identity_sha = validate_model_identity(identity, expected_parameters=manifest["parameters"]) if isinstance(identity, dict) else ""
        except ContractError as exc:
            failures.extend(exc.errors)
            identity_sha = ""
        if not identity_sha or runtime_record.get("resolved_model_identity_sha256") != identity_sha or p5_record.get("resolved_model_identity_sha256") != identity_sha:
            failures.append(error("$.call_record.resolved_model_identity_sha256", "Resolved reviewer model identity binding mismatch", "authority_hash_mismatch"))
        expected_request_sha = transport_request_sha256(call_manifest_sha256=manifest_sha, manifest=manifest, model_identity_sha256=identity_sha) if identity_sha else ""
        if not expected_request_sha or runtime_record.get("transport_request_sha256") != expected_request_sha or p5_record.get("transport_request_sha256") != expected_request_sha:
            failures.append(error("$.call_record.transport_request_sha256", "Transport request envelope binding mismatch", "authority_hash_mismatch"))
        try:
            validate_runtime_timestamps(runtime_record)
        except ContractError as exc:
            failures.extend(exc.errors)
        ledger_path = root / "call-ledger.json"
        if not ledger_path.is_file() or p5_record.get("call_ledger_sha256") != sha256_file(ledger_path):
            failures.append(error("$.call_record.call_ledger_sha256", "Live call ledger binding mismatch", "authority_hash_mismatch"))
        else:
            ledger = load_json(ledger_path)
            matches = [item for item in ledger.get("calls", []) if item.get("call_id") == p5_record.get("call_id") and item.get("role") == "reviewer" and item.get("live") is True and item.get("status") in {"succeeded", "completed"}]
            if len(matches) != 1:
                failures.append(error("$.call_ledger", "Ledger does not prove exactly one successful live reviewer call", "call_record"))
    elif p5_record.get("call_ledger_sha256") is not None or "call-ledger.json" in actual_entries:
        failures.append(error("$.call_record.call_ledger_sha256", "Fixture evidence cannot contain a live call ledger", "call_record"))
    if runtime_record.get("status") != "succeeded" or runtime_record.get("parent_context_id") is not None:
        failures.append(error("$.runtime_call_record", "Reviewer runtime did not complete in a fresh context", "call_record"))
    if sha256_file(root / "system_prompt.md") != comparisons["prompt_sha256"]:
        failures.append(error("$.system_prompt", "System prompt hash mismatch", "authority_hash_mismatch"))
    if manifest.get("selected_output_schema") != output_schema.name or manifest.get("selected_output_schema_sha256") != comparisons["response_schema_sha256"]:
        failures.append(error("$.call_manifest.selected_output_schema", "Selected response schema mismatch", "call_record"))
    validate_schema("deck_consistency_reviewer_response" if expected_profile == "deck_consistency" else "exception_reviewer_response", finalized, SCHEMA_DIR)
    if failures:
        raise ContractError(failures)
    return {"manifest": manifest, "runtime_record": runtime_record, "call_record": p5_record, "response": finalized, "input_hashes": actual_inputs}
