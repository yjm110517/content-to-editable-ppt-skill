from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable

from asset_common import contains_reparse_point
from canonical_artifact import canonical_sha256
from p5_atomic import p5_canonical_bytes
from schema_utils import ContractError, error, is_safe_relative_path, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"

ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)
FILE_MODE = 0o644 << 16
DIR_MODE = 0o755 << 16
CREATE_SYSTEM = 3  # UNIX (fixed for deterministic metadata)
COMPRESSLEVEL = 9


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lock_packaging_runtime() -> dict[str, Any]:
    import zlib
    document = {
        "schema_version": "1.0",
        "artifact_type": "delivery_packaging_runtime_lock",
        "packager": "python.zipfile",
        "python_version": platform.python_version(),
        "zlib_version": zlib.ZLIB_VERSION,
        "zlib_runtime_version": zlib.ZLIB_RUNTIME_VERSION,
        "compression": "deflate",
        "compresslevel": COMPRESSLEVEL,
        "entry_timestamp": "1980-01-01T00:00:00Z",
        "entry_permissions": {"file": "0o644", "directory": "0o755"},
        "entry_order": "lexical",
        "filename_encoding": "utf-8",
        "platform": platform.platform(),
        "create_system": CREATE_SYSTEM,
        "flag_bits_policy": "ascii_names_only",
        "extra_policy": "empty",
        "comment": "",
        "archive_comment": "",
        "allow_zip64": True,
        "directory_entry_policy": "included_for_assets_zip",
    }
    validate_schema("delivery_packaging_runtime_lock", document, SCHEMA_DIR)
    return document


def _verify_lock(document: dict[str, Any]) -> None:
    validate_schema("delivery_packaging_runtime_lock", document, SCHEMA_DIR)
    failures: list[dict[str, str]] = []
    import zlib
    if document["python_version"] != platform.python_version():
        failures.append(error("$.python_version", "packaging python changed", "packaging_runtime_mismatch"))
    if document["zlib_runtime_version"] != zlib.ZLIB_RUNTIME_VERSION:
        failures.append(error("$.zlib_runtime_version", "packaging zlib runtime changed", "packaging_runtime_mismatch"))
    if document["compresslevel"] != COMPRESSLEVEL or document["create_system"] != CREATE_SYSTEM:
        failures.append(error("$.runtime", "packaging parameters changed", "packaging_runtime_mismatch"))
    if failures:
        raise ContractError(failures)


def _deterministic_zip(output: Path, entries: Iterable[tuple[str, bytes]]) -> None:
    ordered = sorted(entries, key=lambda item: item[0])
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=COMPRESSLEVEL, allowZip64=True) as archive:
        for arcname, payload in ordered:
            info = zipfile.ZipInfo(arcname, date_time=ZIP_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = CREATE_SYSTEM
            info.external_attr = FILE_MODE
            info.extra = b""
            info.comment = b""
            archive.writestr(info, payload)
        archive.comment = b""


def _safe_root(path: Path, label: str) -> Path:
    """Validate a directory root: no symlink/reparse point on the path, resolve stays in root."""
    resolved = path.resolve()
    drive = Path(resolved.anchor)
    if contains_reparse_point(resolved, drive):
        raise ContractError([error("$." + label, "path contains a symbolic link or reparse point", "reparse_point")])
    return resolved


def _require_under(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ContractError([error("$." + label, "path escapes its root after resolution", "path_escape")]) from exc
    return resolved


def _verify_packaging_authorization(
    *,
    state: dict[str, Any],
    decision: dict[str, Any] | None,
    candidate_pptx: Path,
    p4_candidate_sha: str,
    qa_report: Path,
    deck_consistency_report: Path,
    roundtrip_report: Path,
    lock_document: dict[str, Any],
) -> None:
    """Pre-flight gate before ANY delivery directory is created (candidate or formal)."""
    failures: list[dict[str, str]] = []
    if decision is not None and state["state"] != "packaging":
        failures.append(error("$.state", f"formal packaging requires packaging state, got {state['state']}", "packaging_state_mismatch"))
    if decision is not None:
        if decision["status"] not in {"pass", "pass_with_warnings"}:
            failures.append(error("$.decision.status", "formal packaging requires pass or pass_with_warnings", "decision_status_mismatch"))
        if decision["status"] == "pass_with_warnings":
            approval = decision.get("warning_approval")
            if not approval or not approval.get("warning_acceptance_sha256"):
                failures.append(error("$.decision.warning_approval", "pass_with_warnings requires a valid warning acceptance", "warning_acceptance_missing"))
        if decision["delivered_pptx_sha256"] != file_sha256(candidate_pptx):
            failures.append(error("$.decision.delivered_pptx_sha256", "decision candidate hash does not match the actual candidate file", "candidate_hash_mismatch"))
        if decision["delivered_pptx_sha256"] != p4_candidate_sha:
            failures.append(error("$.decision.delivered_pptx_sha256", "decision candidate hash does not match the P4 candidate hash", "candidate_hash_mismatch"))
        for key, path in (("qa_report_sha256", qa_report), ("roundtrip_report_sha256", roundtrip_report), ("deck_consistency_report_sha256", deck_consistency_report)):
            if decision["references"].get(key) != canonical_sha256(load_json(path)):
                failures.append(error(f"$.decision.references.{key}", "decision reference hash does not match the actual file", "authority_hash_mismatch"))
    else:
        # candidate mode: no decision exists yet (deterministic phase)
        pass
    frozen_lock = state.get("current_artifacts", {}).get("delivery_packaging_runtime_lock_sha256")
    if frozen_lock and frozen_lock != canonical_sha256(lock_document):
        failures.append(error("$.delivery_packaging_runtime_lock_sha256", "runtime lock hash does not match the state-frozen lock", "packaging_runtime_mismatch"))
    if failures:
        raise ContractError(failures)


def _install_atomically(stage: Path, target: Path, dist_root: Path) -> bool:
    """Move stage to target atomically; idempotent only when the existing target matches exactly."""
    if target.exists():
        existing = {path.name: file_sha256(path) for path in target.iterdir() if path.is_file()}
        staged = {path.name: file_sha256(path) for path in stage.iterdir() if path.is_file()}
        if existing != staged:
            raise ContractError([error("$.target", "existing delivery directory conflicts with accepted output", "output_conflict")])
        return False
    # Re-validate the target absolute path before moving (never delete outside the dist root).
    _require_under(target, dist_root, "target")
    shutil.move(str(stage), str(target))
    return True


def _rollback(target: Path, dist_root: Path) -> None:
    """Rollback an installed delivery directory; only after re-validating the path is inside dist_root."""
    _require_under(target, dist_root, "target")
    if target.exists():
        shutil.rmtree(target)


def build_package_candidate(
    *,
    deck_id: str,
    output_name: str,
    candidate_pptx: Path,
    work_root: Path,
    lock_document: dict[str, Any],
    previews: dict[str, Path],
    assets: list[tuple[str, Path]],
    asset_manifest: Path,
    preview_manifest: Path,
    qa_report: Path,
    roundtrip_report: Path,
    authority_hashes: dict[str, str],
) -> dict[str, Any]:
    """Deterministic phase: build the 6-file package candidate in work/<deck>/delivery-package-candidate/.
    delivery_forbidden = true; formal_decision_sha256 = null; no decision or deck-consistency report inside."""
    _verify_lock(lock_document)
    if not is_safe_relative_path(output_name, filename_only=True):
        raise ContractError([error("$.output_name", "output-name must be a safe single path component", "unsafe_path")])
    work = _safe_root(work_root, "work_root")
    work.mkdir(parents=True, exist_ok=True)
    candidate_dir = work / deck_id / "delivery-package-candidate"
    stage = Path(tempfile.mkdtemp(prefix=f".{output_name}-candidate-", dir=work))
    try:
        names = {
            f"{output_name}_editable.pptx": candidate_pptx,
            f"{output_name}_qa_report.json": qa_report,
            f"{output_name}_roundtrip_report.json": roundtrip_report,
        }
        for name, source in names.items():
            shutil.copy2(source, stage / name)

        previews_zip = stage / f"{output_name}_previews.zip"
        preview_entries = [(arcname, source.read_bytes()) for arcname, source in previews.items()]
        # preview manifest must be included inside the zip
        preview_entries.append(("preview-manifest.json", preview_manifest.read_bytes()))
        _deterministic_zip(previews_zip, preview_entries)

        assets_zip = stage / f"{output_name}_assets.zip"
        asset_entries = [(arcname, source.read_bytes()) for arcname, source in sorted(assets, key=lambda item: item[0])]
        asset_entries.append(("asset-manifest.json", asset_manifest.read_bytes()))
        _deterministic_zip(assets_zip, asset_entries)

        candidate_files = {name: file_sha256(stage / name) for name in sorted(names)}
        candidate_files[f"{output_name}_previews.zip"] = file_sha256(previews_zip)
        candidate_files[f"{output_name}_assets.zip"] = file_sha256(assets_zip)

        candidate_manifest = {
            "schema_version": "1.0",
            "artifact_type": "delivery_package_candidate",
            "deck_id": deck_id,
            "delivery_forbidden": True,
            "live_review_status": "pending",
            "formal_decision_sha256": None,
            "package_candidate_files": candidate_files,
        }
        validate_schema("delivery_package_candidate_manifest", candidate_manifest, SCHEMA_DIR)
        (stage / f"{output_name}_package-candidate-manifest.json").write_bytes(p5_canonical_bytes(candidate_manifest))
        manifest_sha256 = file_sha256(stage / f"{output_name}_package-candidate-manifest.json")
        candidate_files[f"{output_name}_package-candidate-manifest.json"] = manifest_sha256

        final_files = {name: file_sha256(stage / name) for name in sorted(path.name for path in stage.iterdir() if path.is_file())}
        installed = _install_atomically(stage, candidate_dir, work)
        return {
            "candidate_dir": str(candidate_dir),
            "deck_id": deck_id,
            "delivery_forbidden": True,
            "formal_delivery_created": False,
            "package_candidate_hash_closure": "pass",
            "package_candidate_manifest_sha256": manifest_sha256,
            "files": final_files,
            "idempotent": not installed,
            "authority_hashes": authority_hashes,
        }
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def verify_package_candidate(*, target: Path, expected_manifest_sha256: str) -> dict[str, Any]:
    root = target.resolve()
    if not root.is_dir() or contains_reparse_point(root, root.parent):
        raise ContractError([error("$.target", "package candidate directory is missing or unsafe", "delivery_integrity")])
    entries = list(root.iterdir())
    if any(item.is_dir() for item in entries) or len(entries) != 6:
        raise ContractError([error("$.target", "package candidate must contain exactly six files", "delivery_integrity")])
    manifests = [item for item in entries if item.name.endswith("_package-candidate-manifest.json")]
    if len(manifests) != 1:
        raise ContractError([error("$.target", "package candidate manifest is missing or ambiguous", "delivery_integrity")])
    manifest_path = manifests[0]
    manifest_sha = file_sha256(manifest_path)
    if manifest_sha != expected_manifest_sha256:
        raise ContractError([error("$.manifest", "package candidate manifest self-hash mismatch", "delivery_integrity")])
    manifest = load_json(manifest_path)
    validate_schema("delivery_package_candidate_manifest", manifest, SCHEMA_DIR)
    if manifest.get("delivery_forbidden") is not True or manifest.get("formal_decision_sha256") is not None:
        raise ContractError([error("$.manifest", "package candidate authority flags are invalid", "delivery_integrity")])
    sibling_paths = {item.name: item for item in entries if item != manifest_path}
    if set(sibling_paths) != set(manifest["package_candidate_files"]):
        raise ContractError([error("$.manifest.package_candidate_files", "package candidate file set mismatch", "delivery_integrity")])
    failures = [name for name, digest in manifest["package_candidate_files"].items() if file_sha256(sibling_paths[name]) != digest]
    if failures:
        raise ContractError([error("$.manifest.package_candidate_files", f"package candidate sibling hash mismatch: {failures}", "delivery_integrity")])
    return {"status": "pass", "manifest_sha256": manifest_sha, "files": sorted(sibling_paths)}


def package_formal_delivery(
    *,
    deck_id: str,
    output_name: str,
    candidate_pptx: Path,
    dist_root: Path,
    lock_document: dict[str, Any],
    previews: dict[str, Path],
    assets: list[tuple[str, Path]],
    asset_manifest: Path,
    preview_manifest: Path,
    qa_report: Path,
    deck_consistency_report: Path,
    roundtrip_report: Path,
    decision: Path,
    state: dict[str, Any],
    p4_candidate_sha: str,
    authority_hashes: dict[str, str],
    reviewer_summary: dict[str, Any],
) -> dict[str, Any]:
    """Formal 7-file delivery: only after a valid live (or fixture-marked) review consumption.
    Runs the full authorization gate BEFORE creating any directory; rolls back on state failure."""
    decision_doc = load_json(decision)
    validate_schema("deck_delivery_decision", decision_doc, SCHEMA_DIR)
    _verify_packaging_authorization(
        state=state, decision=decision_doc, candidate_pptx=candidate_pptx, p4_candidate_sha=p4_candidate_sha,
        qa_report=qa_report, deck_consistency_report=deck_consistency_report, roundtrip_report=roundtrip_report,
        lock_document=lock_document,
    )
    dist = _safe_root(dist_root, "dist_root")
    dist.mkdir(parents=True, exist_ok=True)
    target = dist / output_name
    _require_under(target, dist, "target")
    stage = Path(tempfile.mkdtemp(prefix=f".{output_name}-delivery-", dir=dist))
    try:
        names = {
            f"{output_name}_editable.pptx": candidate_pptx,
            f"{output_name}_qa_report.json": qa_report,
            f"{output_name}_deck_consistency_report.json": deck_consistency_report,
            f"{output_name}_delivery_decision.json": decision,
        }
        for name, source in names.items():
            shutil.copy2(source, stage / name)

        previews_zip = stage / f"{output_name}_previews.zip"
        preview_entries = [(arcname, source.read_bytes()) for arcname, source in previews.items()]
        preview_entries.append(("preview-manifest.json", preview_manifest.read_bytes()))
        _deterministic_zip(previews_zip, preview_entries)

        assets_zip = stage / f"{output_name}_assets.zip"
        asset_entries = [(arcname, source.read_bytes()) for arcname, source in sorted(assets, key=lambda item: item[0])]
        asset_entries.append(("asset-manifest.json", asset_manifest.read_bytes()))
        _deterministic_zip(assets_zip, asset_entries)

        delivery_files = {name: file_sha256(stage / name) for name in sorted(names)}
        delivery_files[f"{output_name}_previews.zip"] = file_sha256(previews_zip)
        delivery_files[f"{output_name}_assets.zip"] = file_sha256(assets_zip)

        provenance = {
            "schema_version": "1.0",
            "artifact_type": "delivery_provenance",
            "deck_id": deck_id,
            "p1_to_p4_authority": {
                "p4_state_sha256": authority_hashes.get("p4_state_sha256", ""),
                "p4_manifest_sha256": authority_hashes.get("p4_manifest_sha256", ""),
                "p4_candidate_report_sha256": authority_hashes.get("p4_candidate_report_sha256", ""),
                "p4_drift_report_sha256": authority_hashes.get("p4_drift_report_sha256", ""),
                "p4_render_report_sha256": authority_hashes.get("p4_render_report_sha256", ""),
                "manifest_compatibility_status": "closed",
            },
            "final_integrity": {"p5_final_render_manifest_sha256": authority_hashes.get("p5_final_render_manifest_sha256", "")},
            "roundtrip": {"powerpoint_roundtrip_report_sha256": authority_hashes.get("powerpoint_roundtrip_report_sha256", "")},
            "reviewer": {
                "exception_reviewer_calls": reviewer_summary.get("exception_reviewer_calls", 0),
                "deck_reviewer_calls": reviewer_summary.get("deck_reviewer_calls", 0),
                "unexpected_reviewer_calls": reviewer_summary.get("unexpected_reviewer_calls", 0),
                "deck_consistency_report_sha256": authority_hashes.get("deck_consistency_report_sha256", ""),
                "review_mode": reviewer_summary.get("review_mode", "deterministic_fixture"),
            },
            "decision": {"deck_delivery_decision_sha256": authority_hashes.get("deck_delivery_decision_sha256", ""), "status": decision_doc["status"]},
            "runtime_lock": {"delivery_packaging_runtime_lock_sha256": canonical_sha256(lock_document)},
            "delivery_files": {name: delivery_files[name] for name in sorted(delivery_files)},
        }
        validate_schema("delivery_provenance", provenance, SCHEMA_DIR)
        (stage / f"{output_name}_provenance.json").write_bytes(p5_canonical_bytes(provenance))
        delivery_files[f"{output_name}_provenance.json"] = file_sha256(stage / f"{output_name}_provenance.json")

        final_files = {name: file_sha256(stage / name) for name in sorted(path.name for path in stage.iterdir() if path.is_file())}
        expected = set(delivery_files) | {f"{output_name}_provenance.json"}
        if set(final_files) != expected:
            raise ContractError([error("$.delivery_files", "delivery staging file set is not exact", "delivery_integrity")])
        installed = _install_atomically(stage, target, dist)
        return {
            "dist": str(target),
            "deck_id": deck_id,
            "formal_delivery_created": True,
            "files": final_files,
            "provenance_sha256": final_files[f"{output_name}_provenance.json"],
            "delivered_pptx_sha256": final_files[f"{output_name}_editable.pptx"],
            "idempotent": not installed,
        }
    except Exception:
        _rollback(target, dist)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def verify_delivery(*, target: Path, provenance_expected_sha256: str, dist_root: Path) -> dict[str, Any]:
    """Reverse-verify a delivered directory: closure of the six sibling artifacts and provenance self-hash."""
    _safe_root(dist_root, "dist_root")
    target = _require_under(target.resolve(), dist_root, "target")
    failures: list[dict[str, str]] = []
    files = {path.name: path for path in target.iterdir() if path.is_file()}
    provenance_name = next((name for name in files if name.endswith("_provenance.json")), None)
    if provenance_name is None:
        raise ContractError([error("$.target", "delivery directory has no provenance artifact", "delivery_integrity")])
    provenance = load_json(files[provenance_name])
    validate_schema("delivery_provenance", provenance, SCHEMA_DIR)
    expected_six = set(provenance["delivery_files"])
    actual = {name: file_sha256(path) for name, path in files.items() if name != provenance_name}
    if set(actual) != expected_six:
        failures.append(error("$.delivery_files", "delivery file set differs from provenance", "delivery_integrity"))
    for name, digest in provenance["delivery_files"].items():
        if actual.get(name) != digest:
            failures.append(error(f"$.delivery_files.{name}", "delivery file hash does not match provenance", "delivery_integrity"))
    provenance_self = file_sha256(files[provenance_name])
    if provenance_self != provenance_expected_sha256:
        failures.append(error("$.provenance", "provenance self-hash does not match the recorded state/gate hash", "delivery_integrity"))
    if failures:
        raise ContractError(failures)
    return {"status": "pass", "files": sorted(actual), "provenance_sha256": provenance_self, "delivery_artifact_hash_closure": "pass", "formal_delivery_created": True}
