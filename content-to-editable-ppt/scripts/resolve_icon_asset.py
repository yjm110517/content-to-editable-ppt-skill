from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from defusedxml import ElementTree as SafeET

from asset_common import AssetError
from canonical_artifact import canonical_sha256
from sanitize_svg import local_name, sanitize_manifest
from schema_utils import ContractError, error, is_safe_relative_path, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
EXPECTED_VERSION = "3.46.0"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_once(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ContractError([error(str(path), "immutable artifact already exists", "overwrite_forbidden")])
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(value)
    os.replace(temporary, path)


def validate_p2(manifest_path: Path, wireframe_root: Path) -> tuple[dict[str, Any], str]:
    manifest = load_json(manifest_path)
    validate_schema("markdown_wireframe_manifest", manifest, SCHEMA_DIR)
    if manifest["schema_version"] != "1.1" or manifest["status"] != "accepted":
        raise ContractError([error("$.p2_manifest", "P3.1 requires an accepted P2 1.1 Manifest", "p2_version_blocked")])
    relative = manifest["wireframe_path"]
    if not is_safe_relative_path(relative):
        raise ContractError([error("$.p2_manifest.wireframe_path", "unsafe Markdown path", "unsafe_path")])
    markdown = (wireframe_root / relative).resolve()
    try:
        markdown.relative_to(wireframe_root.resolve())
    except ValueError as exc:
        raise ContractError([error("$.p2_manifest.wireframe_path", "Markdown path escapes wireframe root", "unsafe_path")]) from exc
    if not markdown.is_file() or sha256_file(markdown) != manifest["wireframe_sha256"]:
        raise ContractError([error("$.p2_manifest.wireframe_sha256", "Markdown Authority hash mismatch", "authority_hash_mismatch")])
    return manifest, canonical_sha256(manifest)


def find_visual(manifest: dict[str, Any], visual_ref: str) -> dict[str, Any]:
    matches = [visual for slide in manifest["slides"] for visual in slide["visual_placeholders"] if visual["visual_ref"] == visual_ref]
    if len(matches) != 1 or matches[0]["role"] != "icon":
        raise ContractError([error("$.visual_ref", "Visual Ref must resolve to exactly one P2 icon placeholder", "unknown_visual_ref")])
    return matches[0]


def validate_direction(path: Path, manifest: dict[str, Any], manifest_sha: str) -> dict[str, Any]:
    direction = load_json(path)
    validate_schema("deck_visual_direction", direction, SCHEMA_DIR)
    if direction["deck_id"] != manifest["deck_id"] or direction["p2_manifest_sha256"] != manifest_sha:
        raise ContractError([error("$.visual_direction", "Visual Direction does not bind P2 Authority", "authority_hash_mismatch")])
    return direction


def validate_search_evidence(path: Path, *, visual_ref: str, manifest_sha: str, icon_name: str, selection_method: str) -> dict[str, Any]:
    evidence = load_json(path)
    validate_schema("icon_search_evidence", evidence, SCHEMA_DIR)
    if evidence["visual_ref"] != visual_ref or evidence["p2_manifest_sha256"] != manifest_sha:
        raise ContractError([error("$.search_evidence", "search evidence does not bind the requested P2 placeholder", "authority_hash_mismatch")])
    candidates = [item for item in evidence["top_k"] if item["name"] == icon_name]
    if len(candidates) != 1:
        raise ContractError([error("$.search_evidence.top_k", "selected icon is not a unique Top-K candidate", "selection_not_in_top_k")])
    selected = candidates[0]
    exact_key = "exact_canonical" if selection_method == "exact_canonical" else "exact_official_alias"
    if selection_method in {"exact_canonical", "exact_official_alias"}:
        if evidence["status"] != "auto_selected" or evidence["automatic_icon_name"] != icon_name or not selected["evidence"][exact_key]:
            raise ContractError([error("$.selection_method", "exact selection is not supported by the search evidence", "invalid_selection")])
    elif evidence["status"] != "host_selection_required":
        raise ContractError([error("$.selection_method", "host_from_top_k requires host-selection evidence", "invalid_selection")])
    return evidence


def normalize_svg(content: bytes) -> bytes:
    root = SafeET.fromstring(content)
    if local_name(root.tag) != "svg":
        raise ContractError([error("$.source_svg", "source root must be SVG", "invalid_svg")])
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root.attrib["width"] = "24"
    root.attrib["height"] = "24"
    root.attrib["viewBox"] = "0 0 24 24"
    for element in root.iter():
        element.attrib.pop("class", None)
        ordered = sorted((key, unicodedata.normalize("NFC", value)) for key, value in element.attrib.items())
        element.attrib.clear()
        element.attrib.update(ordered)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True, short_empty_elements=True) + b"\n"


def source_for_record(record: dict[str, Any], vendor_root: Path | None, supplied_source: Path | None = None) -> Path:
    if record["resolution_method"] != "tabler_existing":
        if supplied_source is None:
            raise ContractError([error("$.source_svg", "generated fallback records require the immutable source SVG", "missing_authority")])
        source = supplied_source.resolve()
        if not source.is_file() or sha256_file(source) != record["source_sha256"]:
            raise ContractError([error("$.resolution_record.source_sha256", "generated source does not match immutable record", "source_hash_mismatch")])
        return source
    if vendor_root is None:
        raise ContractError([error("$.vendor_root", "Tabler resolution requires the pinned vendor root", "missing_authority")])
    source = (vendor_root.resolve() / "icons" / "outline" / f"{record['icon_name']}.svg").resolve()
    try:
        source.relative_to(vendor_root.resolve())
    except ValueError as exc:
        raise ContractError([error("$.resolution_record.icon_name", "icon path escapes pinned vendor", "unsafe_path")]) from exc
    if not source.is_file() or sha256_file(source) != record["source_sha256"]:
        raise ContractError([error("$.resolution_record.source_sha256", "pinned Tabler source does not match immutable record", "source_hash_mismatch")])
    return source


def create_record(args: argparse.Namespace) -> dict[str, Any]:
    manifest, manifest_sha = validate_p2(args.p2_manifest.resolve(), args.wireframe_root.resolve())
    find_visual(manifest, args.visual_ref)
    validate_direction(args.visual_direction.resolve(), manifest, manifest_sha)
    evidence = validate_search_evidence(
        args.search_evidence.resolve(),
        visual_ref=args.visual_ref,
        manifest_sha=manifest_sha,
        icon_name=args.icon_name,
        selection_method=args.selection_method,
    )
    selected = next(item for item in evidence["top_k"] if item["name"] == args.icon_name)
    source = (args.vendor_root.resolve() / selected["relative_path"]).resolve()
    try:
        source.relative_to(args.vendor_root.resolve())
    except ValueError as exc:
        raise ContractError([error("$.search_evidence.relative_path", "icon path escapes pinned vendor", "unsafe_path")]) from exc
    if not source.is_file() or sha256_file(source) != selected["source_sha256"]:
        raise ContractError([error("$.search_evidence.source_sha256", "search evidence does not match pinned Tabler source", "source_hash_mismatch")])
    record = {
        "schema_version": "1.0",
        "artifact_type": "icon_resolution_record",
        "visual_ref": args.visual_ref,
        "p2_manifest_sha256": manifest_sha,
        "resolution_method": "tabler_existing",
        "library": "tabler-icons",
        "library_version": EXPECTED_VERSION,
        "icon_name": args.icon_name,
        "source_sha256": sha256_file(source),
        "selection_method": args.selection_method,
        "search_evidence_sha256": canonical_sha256(evidence),
        "created_at_utc": args.created_at_utc,
    }
    validate_schema("icon_resolution", record, SCHEMA_DIR)
    write_once(args.output.resolve(), json_bytes(record))
    return {"resolution_record": str(args.output.resolve()), "resolution_record_sha256": canonical_sha256(record)}


def _stage_materialization(record: dict[str, Any], source: Path, stage_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    asset_dir = stage_root / "assets"
    asset_dir.mkdir(parents=True)
    normalized = normalize_svg(source.read_bytes())
    normalized_path = asset_dir / f"{record['visual_ref']}.normalized.svg"
    normalized_path.write_bytes(normalized)
    record_sha = canonical_sha256(record)
    provenance = {
        "provenance_type": "resolved_svg",
        "visual_ref": record["visual_ref"],
        "resolution_record_sha256": record_sha,
        "source_svg_sha256": record["source_sha256"],
        "normalized_svg_sha256": sha256_bytes(normalized),
        "sanitized_svg_sha256": None,
    }
    entry = {
        "id": record["visual_ref"],
        "type": "svg",
        "path": f"assets/{normalized_path.name}",
        "source": {
            "tabler_existing": "library-resolved",
            "tabler_composition": "composite",
            "programmatic_svg": "programmatic",
        }[record["resolution_method"]],
        "width_px": 24,
        "height_px": 24,
        "size_bytes": len(normalized),
        "sha256": provenance["normalized_svg_sha256"],
        "view_box": "0 0 24 24",
        "recolorable": True,
        "contains_text": False,
        "text_editability_exempt": False,
        "security_status": "pending",
        "provenance": provenance,
    }
    manifest = {"schema_version": "1.4", "assets": [entry]}
    validate_schema("asset_manifest", manifest, SCHEMA_DIR)
    manifest_path = stage_root / "asset_manifest.json"
    manifest_path.write_bytes(json_bytes(manifest))
    report_path = stage_root / "svg_security_report.json"
    sanitize_manifest(argparse.Namespace(
        asset_dir=asset_dir,
        asset_manifest=manifest_path,
        report=report_path,
        schema_dir=SCHEMA_DIR,
        max_svg_bytes=10 * 1024 * 1024,
        log_file=None,
        run_id="p3-materialize",
        iteration=None,
    ))
    final_manifest = load_json(manifest_path)
    validate_schema("asset_manifest", final_manifest, SCHEMA_DIR)
    final_entry = final_manifest["assets"][0]
    if final_entry["provenance"]["sanitized_svg_sha256"] != final_entry["sha256"]:
        raise ContractError([error("$.asset_manifest", "sanitized provenance and asset hash diverged", "authority_hash_mismatch")])
    report = load_json(report_path)
    result = report["results"][0]
    if result.get("status") != "passed" or result.get("sanitized_sha256") != final_entry["sha256"]:
        raise ContractError([error("$.svg_security_report", "real sanitizer report does not bind the output", "security_report_mismatch")])
    return final_manifest, report


def materialize(args: argparse.Namespace) -> dict[str, Any]:
    record = load_json(args.resolution_record.resolve())
    validate_schema("icon_resolution", record, SCHEMA_DIR)
    vendor_root = getattr(args, "vendor_root", None)
    source_svg = getattr(args, "source_svg", None)
    source = source_for_record(record, vendor_root.resolve() if vendor_root else None, source_svg)
    output_dir = args.output_dir.resolve()
    root = output_dir.parent
    destinations = {
        "normalized": output_dir / f"{record['visual_ref']}.normalized.svg",
        "sanitized": output_dir / f"{record['visual_ref']}.sanitized.svg",
        "manifest": root / "asset_manifest.json",
        "report": root / "svg_security_report.json",
        "consumption": root / "consumption-contract.json",
    }
    collisions = [str(path) for path in destinations.values() if path.exists()]
    if collisions:
        raise ContractError([error("$.output", f"materialization output already exists: {collisions[0]}", "overwrite_forbidden")])
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".p3-materialize-", dir=root) as temporary:
        stage_root = Path(temporary)
        manifest, _report = _stage_materialization(record, source, stage_root)
        entry = manifest["assets"][0]
        consumption = {
            "schema_version": "1.0",
            "artifact_type": "resolved_asset_consumption_contract",
            "visual_ref": record["visual_ref"],
            "resolution_record_sha256": canonical_sha256(record),
            "asset_manifest_entry_sha256": canonical_sha256(entry),
            "sanitized_svg_sha256": entry["sha256"],
        }
        validate_schema("resolved_asset_consumption", consumption, SCHEMA_DIR)
        (stage_root / "consumption-contract.json").write_bytes(json_bytes(consumption))
        output_dir.mkdir(parents=True, exist_ok=True)
        staged = {
            "normalized": stage_root / "assets" / destinations["normalized"].name,
            "sanitized": stage_root / "assets" / destinations["sanitized"].name,
            "manifest": stage_root / "asset_manifest.json",
            "report": stage_root / "svg_security_report.json",
            "consumption": stage_root / "consumption-contract.json",
        }
        for key in ("normalized", "sanitized", "report", "consumption", "manifest"):
            os.replace(staged[key], destinations[key])
    return {
        "asset_manifest": str(destinations["manifest"]),
        "security_report": str(destinations["report"]),
        "consumption_contract": str(destinations["consumption"]),
        "sanitized_svg": str(destinations["sanitized"]),
        "sanitized_svg_sha256": manifest["assets"][0]["sha256"],
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    manifest, manifest_sha = validate_p2(args.p2_manifest.resolve(), args.wireframe_root.resolve())
    record = load_json(args.resolution_record.resolve())
    validate_schema("icon_resolution", record, SCHEMA_DIR)
    if record["p2_manifest_sha256"] != manifest_sha:
        raise ContractError([error("$.resolution_record.p2_manifest_sha256", "Resolution Record does not bind current P2 Authority", "authority_hash_mismatch")])
    find_visual(manifest, record["visual_ref"])
    validate_direction(args.visual_direction.resolve(), manifest, manifest_sha)
    if record["resolution_method"] == "tabler_existing":
        if args.search_evidence is None:
            raise ContractError([error("$.search_evidence", "Tabler resolution requires Search Evidence", "missing_authority")])
        evidence = validate_search_evidence(
            args.search_evidence.resolve(), visual_ref=record["visual_ref"], manifest_sha=manifest_sha,
            icon_name=record["icon_name"], selection_method=record["selection_method"],
        )
        if canonical_sha256(evidence) != record["search_evidence_sha256"]:
            raise ContractError([error("$.resolution_record.search_evidence_sha256", "Search Evidence hash mismatch", "authority_hash_mismatch")])
    vendor_root = getattr(args, "vendor_root", None)
    source_svg = getattr(args, "source_svg", None)
    source_for_record(record, vendor_root.resolve() if vendor_root else None, source_svg)
    asset_manifest = load_json(args.asset_manifest.resolve())
    validate_schema("asset_manifest", asset_manifest, SCHEMA_DIR)
    if len(asset_manifest["assets"]) != 1:
        raise ContractError([error("$.asset_manifest.assets", "expected exactly one resolved asset", "asset_count_mismatch")])
    entry = asset_manifest["assets"][0]
    provenance = entry["provenance"]
    if provenance["resolution_record_sha256"] != canonical_sha256(record) or provenance["source_svg_sha256"] != record["source_sha256"]:
        raise ContractError([error("$.asset_manifest.provenance", "Asset provenance does not bind the immutable Resolution Record", "authority_hash_mismatch")])
    sanitized = (args.asset_manifest.resolve().parent / entry["path"]).resolve()
    normalized = args.asset_manifest.resolve().parent / "assets" / f"{record['visual_ref']}.normalized.svg"
    if not normalized.is_file() or sha256_file(normalized) != provenance["normalized_svg_sha256"]:
        raise ContractError([error("$.asset_manifest.provenance.normalized_svg_sha256", "Normalized SVG hash mismatch", "asset_integrity_mismatch")])
    if not sanitized.is_file() or sha256_file(sanitized) != entry["sha256"] or provenance["sanitized_svg_sha256"] != entry["sha256"]:
        raise ContractError([error("$.asset_manifest.assets[0].sha256", "Sanitized SVG hash mismatch", "asset_integrity_mismatch")])
    report = load_json(args.security_report.resolve())
    matching = [item for item in report.get("results", []) if item.get("asset_id") == entry["id"]]
    if len(matching) != 1 or matching[0].get("status") != "passed" or matching[0].get("sanitized_sha256") != entry["sha256"]:
        raise ContractError([error("$.svg_security_report", "Sanitizer report does not bind the asset", "security_report_mismatch")])
    consumption = load_json(args.consumption_contract.resolve())
    validate_schema("resolved_asset_consumption", consumption, SCHEMA_DIR)
    expected = {
        "resolution_record_sha256": canonical_sha256(record),
        "asset_manifest_entry_sha256": canonical_sha256(entry),
        "sanitized_svg_sha256": entry["sha256"],
    }
    if any(consumption[key] != value for key, value in expected.items()):
        raise ContractError([error("$.consumption_contract", "Consumption Contract hash chain mismatch", "authority_hash_mismatch")])
    return {"visual_ref": record["visual_ref"], "sanitized_svg_sha256": entry["sha256"], "status": "verified"}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Resolve and materialize P3.1 icon assets")
    sub = result.add_subparsers(dest="action", required=True)
    record = sub.add_parser("create-record")
    record.add_argument("--p2-manifest", type=Path, required=True)
    record.add_argument("--wireframe-root", type=Path, required=True)
    record.add_argument("--visual-direction", type=Path, required=True)
    record.add_argument("--search-evidence", type=Path, required=True)
    record.add_argument("--visual-ref", required=True)
    record.add_argument("--icon-name", required=True)
    record.add_argument("--selection-method", choices=["exact_canonical", "exact_official_alias", "host_from_top_k"], required=True)
    record.add_argument("--vendor-root", type=Path, required=True)
    record.add_argument("--created-at-utc", required=True)
    record.add_argument("--output", type=Path, required=True)
    material = sub.add_parser("materialize")
    material.add_argument("--resolution-record", type=Path, required=True)
    material.add_argument("--vendor-root", type=Path)
    material.add_argument("--source-svg", type=Path)
    material.add_argument("--output-dir", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--p2-manifest", type=Path, required=True)
    check.add_argument("--wireframe-root", type=Path, required=True)
    check.add_argument("--visual-direction", type=Path, required=True)
    check.add_argument("--search-evidence", type=Path)
    check.add_argument("--resolution-record", type=Path, required=True)
    check.add_argument("--vendor-root", type=Path)
    check.add_argument("--source-svg", type=Path)
    check.add_argument("--asset-manifest", type=Path, required=True)
    check.add_argument("--security-report", type=Path, required=True)
    check.add_argument("--consumption-contract", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        actions = {"create-record": create_record, "materialize": materialize, "verify": verify}
        outputs = actions[args.action](args)
        print(json.dumps({"status": "ok", "outputs": outputs}, ensure_ascii=False))
        return 0
    except (ContractError, AssetError, OSError, ValueError, ET.ParseError) as exc:
        if isinstance(exc, ContractError):
            errors = exc.errors
        elif isinstance(exc, AssetError):
            errors = [{"path": exc.detail.get("path", "$"), "code": exc.detail.get("code", "resolution_error"), "message": exc.detail["message"]}]
        else:
            errors = [{"path": "$", "code": "resolution_error", "message": str(exc)}]
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
