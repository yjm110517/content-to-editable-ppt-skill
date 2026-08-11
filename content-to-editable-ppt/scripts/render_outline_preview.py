from __future__ import annotations

import argparse
import json
from pathlib import Path

from schema_utils import load_json, validate_schema


def render(candidate: dict) -> str:
    lines = [f"# Candidate Outline — {candidate['deck_id']}", "", f"Revision: {candidate['revision']}", ""]
    for page in candidate["pages"]:
        lines.extend([
            f"## {page['order']:02d}. {page['title']['text']}", "",
            f"- Slide ID: `{page['slide_id']}`",
            f"- Role: {page['role']}",
            f"- Purpose: {page['purpose']}",
            f"- Key message: {page['key_message']}",
            f"- Visual intent: {page['visual_intent']}", "",
            "Final page text:", "",
        ])
        for block in page["content_blocks"]:
            lines.append(f"- [{block['content_ref']}] {block['text']}")
        lines.append("")
    lines.extend(["---", "", "This preview is a presentation of the Candidate artifact. Editing this Markdown does not change the authority artifact.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a deterministic user-visible P1 outline preview")
    parser.add_argument("--outline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate = load_json(args.outline.resolve())
    validate_schema("candidate_outline", candidate, Path(__file__).resolve().parents[1] / "schemas")
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(render(candidate), encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(args.output.resolve()), "pages": len(candidate["pages"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
