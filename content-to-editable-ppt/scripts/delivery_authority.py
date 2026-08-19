from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_file(path: Path, json_path: str) -> Path:
    if not path.is_file():
        raise ContractError([error(json_path, "required authority file is missing", "missing_authority")])
    return path.resolve()


def load_delivery_authority(
    *,
    p4_state_path: Path,
    p4_manifest_path: Path,
    p4_candidate_report_path: Path,
    p4_drift_report_path: Path,
    p4_render_report_path: Path,
    p4_candidate_pptx: Path,
) -> dict[str, Any]:
    """Load and cross-validate the P4 Authority Bundle consumed by P5."""
    p4_state = load_json(_require_file(p4_state_path, "$.p4_state"))
    p4_manifest = load_json(_require_file(p4_manifest_path, "$.p4_manifest"))
    p4_candidate_report = load_json(_require_file(p4_candidate_report_path, "$.p4_candidate_report"))
    p4_drift_report = load_json(_require_file(p4_drift_report_path, "$.p4_drift_report"))
    p4_render_report = load_json(_require_file(p4_render_report_path, "$.p4_render_report"))
    validate_schema("reconstruction_deck_state", p4_state, SCHEMA_DIR)
    validate_schema("reconstruction_manifest", p4_manifest, SCHEMA_DIR)
    validate_schema("candidate_deck_report", p4_candidate_report, SCHEMA_DIR)
    validate_schema("post_assembly_drift_report", p4_drift_report, SCHEMA_DIR)

    failures: list[dict[str, str]] = []
    if p4_state["state"] != "p4_complete":
        failures.append(error("$.p4_state.state", "P5 requires p4_complete", "authority_state_mismatch"))
    deck_ids = {p4_state.get("deck_id"), p4_manifest.get("deck_id"), p4_candidate_report.get("deck_id"), p4_drift_report.get("deck_id")}
    if len(deck_ids) != 1:
        failures.append(error("$.deck_id", "P4 authority artifacts must share one deck id", "authority_deck_mismatch"))
    deck_id = next(iter(deck_ids)) if len(deck_ids) == 1 else None

    frozen = p4_state.get("current_artifacts", {})
    # Legacy P4 hash contract (Compatibility View): the P4 state binds the manifest
    # CANONICAL hash while the P4 candidate report records the manifest FILE byte hash.
    # Both must be validated separately; neither may be skipped or marked "historical".
    manifest_file_sha = file_sha256(p4_manifest_path)
    manifest_canonical = canonical_sha256(p4_manifest)
    legacy_candidate_manifest = p4_candidate_report.get("reconstruction_manifest_sha256")
    state_manifest = frozen.get("reconstruction_manifest_sha256")
    if not legacy_candidate_manifest or not state_manifest:
        failures.append(error("$.reconstruction_manifest", "P4 manifest hashes are missing", "authority_hash_mismatch"))
    if legacy_candidate_manifest != manifest_file_sha:
        failures.append(error("$.p4_candidate_report.reconstruction_manifest_sha256", "candidate report manifest FILE hash does not match the manifest file", "authority_hash_mismatch"))
    if state_manifest != manifest_canonical:
        failures.append(error("$.p4_state.current_artifacts.reconstruction_manifest_sha256", "P4 state manifest CANONICAL hash does not match the manifest", "authority_hash_mismatch"))
    if frozen.get("candidate_deck_sha256") != file_sha256(p4_candidate_pptx):
        failures.append(error("$.p4_state.current_artifacts.candidate_deck_sha256", "P4 state does not bind the candidate deck file", "authority_hash_mismatch"))
    if p4_candidate_report.get("candidate_pptx_sha256") != frozen.get("candidate_deck_sha256"):
        failures.append(error("$.p4_candidate_report.candidate_pptx_sha256", "candidate report does not match P4 state hash", "authority_hash_mismatch"))
    if p4_drift_report.get("candidate_deck_sha256") != frozen.get("candidate_deck_sha256"):
        failures.append(error("$.p4_drift_report.candidate_deck_sha256", "drift report does not match P4 candidate hash", "authority_hash_mismatch"))
    if p4_drift_report.get("status") != "pass" or p4_drift_report.get("post_assembly_slide_drift") or p4_drift_report.get("unexpected_assembly_mutation"):
        failures.append(error("$.p4_drift_report.status", "P4 post-assembly drift gate must be pass", "assembly_mutation"))
    if p4_render_report.get("ppt_sha256") != frozen.get("candidate_deck_sha256"):
        failures.append(error("$.p4_render_report.ppt_sha256", "P4 render report does not match candidate deck", "authority_hash_mismatch"))
    if p4_render_report.get("status") != "pass":
        failures.append(error("$.p4_render_report.status", "P4 render must be pass", "render_gate"))
    if failures:
        raise ContractError(failures)
    compatibility_view = {
        "legacy_candidate_manifest_file_sha256": legacy_candidate_manifest,
        "manifest_file_sha256": manifest_file_sha,
        "manifest_canonical_sha256": manifest_canonical,
        "state_manifest_canonical_sha256": state_manifest,
        "status": "closed",
    }
    return {
        "deck_id": deck_id,
        "p4_state": p4_state,
        "p4_manifest": p4_manifest,
        "p4_candidate_report": p4_candidate_report,
        "p4_drift_report": p4_drift_report,
        "p4_render_report": p4_render_report,
        "p4_state_sha256": canonical_sha256(p4_state),
        "p4_manifest_sha256": canonical_sha256(p4_manifest),
        "p4_candidate_report_sha256": canonical_sha256(p4_candidate_report),
        "p4_drift_report_sha256": canonical_sha256(p4_drift_report),
        "p4_render_report_sha256": canonical_sha256(p4_render_report),
        "p4_candidate_pptx": p4_candidate_pptx.resolve(),
        "p4_candidate_pptx_sha256": frozen["candidate_deck_sha256"],
        "manifest_compatibility": compatibility_view,
    }
