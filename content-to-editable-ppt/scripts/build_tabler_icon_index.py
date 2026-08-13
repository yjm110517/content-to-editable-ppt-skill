from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path


EXPECTED_VERSION = "3.46.0"
EXPECTED_COMMIT = "8ac7d81b72ece11072ef25ea9fd92e80c6f3c9fc"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_index(vendor_root: Path) -> dict:
    aliases_value = json.loads((vendor_root / "aliases.json").read_text(encoding="utf-8"))
    aliases = aliases_value.get("outline", {})
    reverse: dict[str, list[str]] = {}
    for alias, canonical in aliases.items():
        reverse.setdefault(canonical, []).append(alias)
    entries = []
    for path in sorted((vendor_root / "icons" / "outline").glob("*.svg"), key=lambda value: value.name):
        name = unicodedata.normalize("NFC", path.stem)
        entries.append({
            "name": name,
            "aliases": sorted(unicodedata.normalize("NFC", value) for value in reverse.get(name, [])),
            "relative_path": f"icons/outline/{path.name}",
            "source_sha256": digest(path),
        })
    if len(entries) != 5130 or len({item["name"] for item in entries}) != len(entries):
        raise ValueError("Pinned Tabler outline set is incomplete or contains duplicate names")
    return {
        "schema_version": "1.0",
        "artifact_type": "tabler_icon_index",
        "library": "tabler-icons",
        "library_version": EXPECTED_VERSION,
        "source_commit": EXPECTED_COMMIT,
        "icon_count": len(entries),
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic Tabler Outline index")
    parser.add_argument("--vendor-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    index = build_index(args.vendor_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": "ok", "icons": index["icon_count"], "output": str(args.output.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
