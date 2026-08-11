from __future__ import annotations

import argparse
import copy
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
TOOL_VERSION = "1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def normalized_text_item(item: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(item)
    result["text"] = normalize_text(result["text"])
    return result


def content_payload(page: dict[str, Any]) -> dict[str, Any]:
    return {
        "slide_id": page["slide_id"],
        "order": page["order"],
        "title": normalized_text_item(page["title"]),
        "content_blocks": [normalized_text_item(item) for item in page["content_blocks"]],
    }


def project_document(approved: dict[str, Any], page: dict[str, Any], *, frozen_at_utc: str, parent_sha256: str | None = None) -> dict[str, Any]:
    approved_hash = canonical_sha256(approved)
    payload = content_payload(page)
    return {
        "schema_version": "1.0",
        "canonicalization_version": "p1-rfc8785-nfc-1",
        "artifact_id": f"{approved['deck_id']}-{page['slide_id']}-content-r{approved['revision']}",
        "deck_id": approved["deck_id"],
        "slide_id": page["slide_id"],
        "order": page["order"],
        "revision": approved["revision"],
        "parent_sha256": parent_sha256,
        "approved_outline_revision": approved["revision"],
        "approved_outline_sha256": approved_hash,
        "confirmation_id": approved["confirmation_id"],
        "projection": {
            "tool_version": TOOL_VERSION,
            "input_sha256": approved_hash,
            "output_content_sha256": canonical_sha256(payload),
        },
        "title": payload["title"],
        "content_blocks": payload["content_blocks"],
        "status": "frozen",
        "frozen_at_utc": frozen_at_utc,
    }


def verify_projection(approved: dict[str, Any], projected: dict[str, Any]) -> None:
    validate_schema("approved_slide_content", projected, SCHEMA_DIR)
    failures: list[dict[str, str]] = []
    page = next((item for item in approved["pages"] if item["slide_id"] == projected["slide_id"]), None)
    if page is None:
        failures.append(error("$.slide_id", "projected slide is not present in the Approved Outline"))
    else:
        payload = content_payload(page)
        if projected["order"] != payload["order"] or projected["title"] != payload["title"] or projected["content_blocks"] != payload["content_blocks"]:
            failures.append(error("$", "projected content differs from the Approved Outline"))
        if projected["projection"]["output_content_sha256"] != canonical_sha256(payload):
            failures.append(error("$.projection.output_content_sha256", "projected content hash is invalid"))
    approved_hash = canonical_sha256(approved)
    if projected["approved_outline_sha256"] != approved_hash or projected["projection"]["input_sha256"] != approved_hash:
        failures.append(error("$.approved_outline_sha256", "projection does not bind the Approved Outline"))
    if failures:
        raise ContractError(failures)


def load_parent_hashes(parent_content_dir: Path | None) -> dict[str, str]:
    if parent_content_dir is None:
        return {}
    manifest = load_json(parent_content_dir / "projection-manifest.json")
    result: dict[str, str] = {}
    for item in manifest["slides"]:
        document = load_json(parent_content_dir / item["path"])
        validate_schema("approved_slide_content", document, SCHEMA_DIR)
        digest = canonical_sha256(document)
        if digest != item["sha256"]:
            raise ContractError([error("$.slides", f"parent content hash mismatch: {item['slide_id']}")])
        result[item["slide_id"]] = digest
    return result


def build_projection(approved: dict[str, Any], *, frozen_at_utc: str | None = None, parent_hashes: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_schema("approved_outline", approved, SCHEMA_DIR)
    timestamp = frozen_at_utc or utc_now()
    parents = parent_hashes or {}
    slides = [project_document(approved, page, frozen_at_utc=timestamp, parent_sha256=parents.get(page["slide_id"])) for page in approved["pages"]]
    for slide in slides:
        verify_projection(approved, slide)
    manifest = {
        "schema_version": "1.0",
        "canonicalization_version": "p1-rfc8785-nfc-1",
        "deck_id": approved["deck_id"],
        "revision": approved["revision"],
        "approved_outline_sha256": canonical_sha256(approved),
        "slides": [
            {"slide_id": slide["slide_id"], "order": slide["order"], "path": f"{slide['slide_id']}-r{slide['revision']}.json", "sha256": canonical_sha256(slide)}
            for slide in slides
        ],
    }
    return slides, manifest


def write_projection(output_dir: Path, slides: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    targets = [output_dir / item["path"] for item in manifest["slides"]]
    targets.append(output_dir / "projection-manifest.json")
    existing = [path for path in targets if path.exists()]
    if existing:
        raise FileExistsError(f"projection refuses to overwrite: {existing[0]}")
    output_dir.mkdir(parents=True, exist_ok=True)
    for target, slide in zip(targets[:-1], slides):
        target.write_text(json.dumps(slide, ensure_ascii=False, indent=2), encoding="utf-8")
    targets[-1].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministically project Approved Outline text into frozen slide content")
    parser.add_argument("--outline", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timestamp-utc")
    parser.add_argument("--parent-content-dir", type=Path)
    args = parser.parse_args()
    try:
        approved = load_json(args.outline.resolve())
        if approved["revision"] > 1 and args.parent_content_dir is None:
            raise ContractError([error("$", "approved outline revision requires --parent-content-dir")])
        slides, manifest = build_projection(approved, frozen_at_utc=args.timestamp_utc, parent_hashes=load_parent_hashes(args.parent_content_dir.resolve()) if args.parent_content_dir else None)
        write_projection(args.output_dir.resolve(), slides, manifest)
        print(json.dumps({"status": "ok", "slides": len(slides), "manifest_sha256": canonical_sha256(manifest)}, ensure_ascii=False))
        return 0
    except (ContractError, FileExistsError) as exc:
        errors = exc.errors if isinstance(exc, ContractError) else [{"code": "overwrite_forbidden", "message": str(exc)}]
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
