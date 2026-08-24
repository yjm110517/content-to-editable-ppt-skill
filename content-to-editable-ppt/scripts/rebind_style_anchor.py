from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_once(path: Path, document: dict[str, Any]) -> None:
    if path.exists():
        raise ContractError([error(str(path), "immutable output exists", "overwrite_forbidden")])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def rebind(args: argparse.Namespace) -> dict[str, Any]:
    if args.compatibility_output.exists() or args.anchor_output.exists():
        raise ContractError([error("$", "immutable rebind output exists", "overwrite_forbidden")])
    old_package = load_json(args.old_prompt_package); validate_schema("deck_prompt_package", old_package, SCHEMA_DIR)
    new_package = load_json(args.new_prompt_package); validate_schema("deck_prompt_package", new_package, SCHEMA_DIR)
    anchor = load_json(args.old_anchor_record); validate_schema("style_anchor_record", anchor, SCHEMA_DIR)
    layer = load_json(args.generated_layer_record); validate_schema("generated_visual_layer_record", layer, SCHEMA_DIR)
    mapping = load_json(args.element_map); validate_schema("design_element_map", mapping, SCHEMA_DIR)
    preview = load_json(args.final_preview_record); validate_schema("final_design_preview_record", preview, SCHEMA_DIR)
    feedback = load_json(args.feedback); validate_schema("style_anchor_feedback", feedback, SCHEMA_DIR)
    failures: list[dict[str, str]] = []
    deck_id, slide_id = anchor["deck_id"], anchor["slide_id"]
    if any(item.get("deck_id") != deck_id for item in (old_package, new_package, layer, mapping, preview, feedback)):
        failures.append(error("$", "Anchor compatibility inputs contain another Deck", "deck_mismatch"))
    if any(item.get("slide_id") != slide_id for item in (layer, mapping, preview, feedback)):
        failures.append(error("$", "Anchor compatibility inputs contain another Slide", "slide_mismatch"))
    old_slide = next((item for item in old_package["slides"] if item["slide_id"] == slide_id), None)
    new_slide = next((item for item in new_package["slides"] if item["slide_id"] == slide_id), None)
    if old_slide is None or new_slide is None:
        failures.append(error("$.slides", "Anchor slide is missing from a Prompt Package", "slide_set_mismatch"))
    elif not new_slide["reused"] or old_slide["prompt_input_sha256"] != new_slide["prompt_input_sha256"] or old_slide["prompt_sha256"] != new_slide["prompt_sha256"] or old_slide["prompt"] != new_slide["prompt"]:
        failures.append(error("$.slides", "Anchor page Prompt input changed; re-generation is required", "anchor_prompt_changed"))
    for field in ("deck_visual_system_sha256", "text_footprint_manifest_sha256", "approved_outline_sha256", "slide_content_manifest_sha256", "p3_icon_asset_index_sha256"):
        if old_package[field] != new_package[field]:
            failures.append(error(f"$.{field}", "Anchor Authority changed; compatibility rebind is forbidden", "authority_hash_mismatch"))
    if anchor["deck_prompt_package_sha256"] != canonical_sha256(old_package) or mapping["prompt_package_sha256"] != canonical_sha256(old_package):
        failures.append(error("$.old_prompt_package", "Old Anchor evidence does not bind the old Prompt Package", "authority_hash_mismatch"))
    if layer["prompt_sha256"] != (old_slide or {}).get("prompt_sha256") or layer["image_sha256"] != anchor["generated_layer_sha256"] or _sha_file(args.generated_layer_image) != layer["image_sha256"]:
        failures.append(error("$.generated_layer", "Generated Layer evidence is stale or tampered", "authority_hash_mismatch"))
    if canonical_sha256(mapping) != anchor["element_map_sha256"] or mapping["generated_layer_sha256"] != layer["image_sha256"]:
        failures.append(error("$.element_map", "Element Map does not bind the approved Generated Layer", "authority_hash_mismatch"))
    if preview["final_preview_sha256"] != anchor["final_preview_sha256"]:
        failures.append(error("$.final_preview", "Final Preview Record does not bind the approved Anchor", "authority_hash_mismatch"))
    if preview["generated_layer_sha256"] != layer["image_sha256"] or preview["element_map_sha256"] != canonical_sha256(mapping) or _sha_file(args.final_preview_image) != preview["final_preview_sha256"]:
        failures.append(error("$.final_preview", "Final Preview evidence is stale or tampered", "authority_hash_mismatch"))
    if canonical_sha256(feedback) != anchor["feedback_sha256"] or feedback["decision"] != "accepted" or feedback["final_preview_sha256"] != preview["final_preview_sha256"]:
        failures.append(error("$.feedback", "User approval does not bind the current Final Preview", "confirmation_required"))
    if failures:
        raise ContractError(failures)
    record = {
        "schema_version": "1.0", "artifact_type": "storyboard_anchor_compatibility_record",
        "deck_id": deck_id, "slide_id": slide_id,
        "old_prompt_package_sha256": canonical_sha256(old_package), "new_prompt_package_sha256": canonical_sha256(new_package),
        "slide_prompt_input_sha256": new_slide["prompt_input_sha256"], "slide_prompt_sha256": new_slide["prompt_sha256"],
        "deck_visual_system_sha256": new_package["deck_visual_system_sha256"], "text_footprint_manifest_sha256": new_package["text_footprint_manifest_sha256"],
        "old_anchor_record_sha256": canonical_sha256(anchor), "generated_layer_record_sha256": canonical_sha256(layer),
        "element_map_sha256": canonical_sha256(mapping), "final_preview_record_sha256": canonical_sha256(preview),
        "generated_layer_sha256": layer["image_sha256"], "final_preview_sha256": preview["final_preview_sha256"], "status": "compatible",
    }
    validate_schema("storyboard_anchor_compatibility_record", record, SCHEMA_DIR)
    rebound = copy.deepcopy(anchor); rebound["deck_prompt_package_sha256"] = canonical_sha256(new_package)
    validate_schema("style_anchor_record", rebound, SCHEMA_DIR)
    _write_once(args.compatibility_output, record); _write_once(args.anchor_output, rebound)
    return {"compatibility_record_sha256": canonical_sha256(record), "rebound_anchor_sha256": canonical_sha256(rebound)}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Deterministically rebind an unchanged approved Style Anchor")
    for flag in ("old-prompt-package", "new-prompt-package", "old-anchor-record", "generated-layer-record", "generated-layer-image", "element-map", "final-preview-record", "final-preview-image", "feedback", "compatibility-output", "anchor-output"):
        result.add_argument("--" + flag, type=Path, required=True)
    return result


def main() -> int:
    try:
        output = rebind(parser().parse_args()); print(json.dumps({"status": "ok", **output}, ensure_ascii=False)); return 0
    except (ContractError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        errors = exc.errors if isinstance(exc, ContractError) else [error("$", str(exc), "anchor_rebind_error")]
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False)); return 4


if __name__ == "__main__":
    raise SystemExit(main())
