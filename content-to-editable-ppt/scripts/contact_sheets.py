from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from schema_utils import ContractError, error


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Compose P5 deck review contact sheets from approved previews and P4 candidate renders.")
    result.add_argument("--deck-id", required=True)
    result.add_argument("--approved-previews", action="append", required=True, help="SLIDE_ID=preview.png")
    result.add_argument("--candidate-renders", action="append", required=True, help="SLIDE_ID=render.png")
    result.add_argument("--output-dir", type=Path, required=True)
    return result


def _pairs(values: list[str], option: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values or []:
        if "=" not in value:
            raise ContractError([error(option, "expected SLIDE_ID=PATH", "cli_error")])
        key, raw = value.split("=", 1)
        if not key or key in result:
            raise ContractError([error(option, "key must be non-empty and unique", "cli_error")])
        result[key] = Path(raw)
    return result


def _sheet(slides: list[tuple[str, Path]], output: Path, title: str) -> dict[str, str]:
    thumbs: list[Image.Image] = []
    for _, path in slides:
        with Image.open(path) as image:
            image.load()
            image.thumbnail((480, 270))
            thumbs.append(image.convert("RGB"))
    if not thumbs:
        raise ContractError([error("$.slides", "contact sheet requires at least one slide", "empty_contact_sheet")])
    cols = min(3, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols
    thumb_w = max(image.width for image in thumbs)
    thumb_h = max(image.height for image in thumbs)
    pad = 24
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * pad, rows * thumb_h + (rows + 1) * pad + 48), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 8), f"{title}  -  {len(slides)} slides", fill="black")
    for index, (slide_id, _) in enumerate(slides):
        col, row = index % cols, index // cols
        x = pad + col * (thumb_w + pad)
        y = 48 + pad + row * (thumb_h + pad)
        sheet.paste(thumbs[index], (x, y))
        draw.text((x, y + thumb_h + 2), slide_id, fill="black")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", compress_level=9)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return {"path": output.name, "sha256": digest, "slides": len(slides)}


def compose_contact_sheets(*, deck_id: str, approved: dict[str, Path], candidates: dict[str, Path], output_dir: Path) -> dict[str, Any]:
    if set(approved) != set(candidates):
        raise ContractError([error("$.slides", "approved previews and candidate renders must cover the same slides", "slide_set_mismatch")])
    ordered = sorted(approved)
    approved_items = [(slide_id, approved[slide_id]) for slide_id in ordered]
    candidate_items = [(slide_id, candidates[slide_id]) for slide_id in ordered]
    approved_sheet = _sheet(approved_items, output_dir / "approved-preview-contact-sheet.png", "Approved Preview")
    candidate_sheet = _sheet(candidate_items, output_dir / "final-candidate-contact-sheet.png", "Final Candidate")
    comparison = output_dir / "approved-vs-final-comparison-sheet.png"
    _sheet(approved_items + candidate_items, comparison, "Approved vs Final")
    comparison_record = {"path": comparison.name, "sha256": hashlib.sha256(comparison.read_bytes()).hexdigest(), "slides": len(approved_items) * 2}
    return {
        "schema_version": "1.0",
        "artifact_type": "contact_sheet_set",
        "deck_id": deck_id,
        "approved_preview_contact_sheet": approved_sheet,
        "final_candidate_contact_sheet": candidate_sheet,
        "approved_vs_final_comparison_sheet": comparison_record,
    }


def main() -> int:
    args = parser().parse_args()
    try:
        result = compose_contact_sheets(deck_id=args.deck_id, approved=_pairs(args.approved_previews, "--approved-previews"), candidates=_pairs(args.candidate_renders, "--candidate-renders"), output_dir=args.output_dir)
        print(json.dumps({"status": "ok", "outputs": result, "error": None}, ensure_ascii=False))
        return 0
    except Exception as exc:
        issues = exc.errors if isinstance(exc, ContractError) else [{"path": "$", "code": "contact_sheet_internal_error", "message": str(exc)}]
        print(json.dumps({"status": "error", "outputs": {}, "error": {"issues": issues}}, ensure_ascii=False))
        return 4 if isinstance(exc, ContractError) else 70


if __name__ == "__main__":
    raise SystemExit(main())
