from __future__ import annotations

import argparse
import difflib
import json
import re
import unicodedata
from pathlib import Path


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold().strip()
    return "-".join(part for part in re.split(r"[^a-z0-9]+", value) if part)


def rank(index: dict, query: str, top_k: int = 8, *, visual_ref: str | None = None, p2_manifest_sha256: str | None = None) -> dict:
    query_key = normalize(query)
    if not query_key:
        raise ValueError("query must contain searchable ASCII terms")
    results = []
    for entry in index["entries"]:
        name = entry["name"]
        aliases = entry["aliases"]
        exact_name = query_key == name
        exact_alias = query_key in aliases
        name_tokens = set(name.split("-"))
        query_tokens = set(query_key.split("-"))
        token_overlap = len(name_tokens & query_tokens)
        prefix = name.startswith(query_key) or query_key.startswith(name)
        substring = query_key in name or name in query_key
        fuzzy = round(difflib.SequenceMatcher(None, query_key, name).ratio() * 100)
        score = (10000 if exact_name else 0) + (9000 if exact_alias else 0) + token_overlap * 200 + (100 if prefix else 0) + (50 if substring else 0) + fuzzy
        if score:
            results.append({**entry, "score": score, "evidence": {"exact_canonical": exact_name, "exact_official_alias": exact_alias, "token_overlap": token_overlap, "prefix": prefix, "substring": substring, "fuzzy": fuzzy}})
    results.sort(key=lambda item: (-item["score"], item["name"]))
    selected = results[:top_k]
    automatic = [item for item in selected if item["evidence"]["exact_canonical"] or item["evidence"]["exact_official_alias"]]
    status = "auto_selected" if len(automatic) == 1 else "host_selection_required"
    result = {"query": query, "normalized_query": query_key, "status": status, "automatic_icon_name": automatic[0]["name"] if status == "auto_selected" else None, "top_k": selected}
    if visual_ref is not None or p2_manifest_sha256 is not None:
        if not visual_ref or not p2_manifest_sha256:
            raise ValueError("visual_ref and p2_manifest_sha256 must be supplied together")
        result = {
            "schema_version": "1.0",
            "artifact_type": "icon_search_evidence",
            "visual_ref": visual_ref,
            "p2_manifest_sha256": p2_manifest_sha256,
            **result,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline deterministic Tabler icon search")
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--visual-ref", required=True)
    parser.add_argument("--p2-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.top_k <= 50:
        parser.error("--top-k must be between 1 and 50")
    result = rank(
        json.loads(args.index.read_text(encoding="utf-8")),
        args.query,
        args.top_k,
        visual_ref=args.visual_ref,
        p2_manifest_sha256=args.p2_manifest_sha256,
    )
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
