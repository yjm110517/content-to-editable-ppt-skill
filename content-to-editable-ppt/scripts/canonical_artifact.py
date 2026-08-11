from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

import rfc8785


CANONICALIZATION_VERSION = "p1-rfc8785-nfc-1"
MAX_SAFE_INTEGER = 9_007_199_254_740_991


class CanonicalArtifactError(ValueError):
    pass


def _reject_constant(value: str) -> None:
    raise CanonicalArtifactError(f"non-finite number is forbidden: {value}")


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalArtifactError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CanonicalArtifactError(f"invalid UTF-8 JSON: {path}") from exc


def normalize_nfc(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise CanonicalArtifactError("integer exceeds the JavaScript safe integer range")
        return value
    if isinstance(value, float):
        raise CanonicalArtifactError("floating-point values are forbidden in P1 authority artifacts")
    if isinstance(value, list):
        return [normalize_nfc(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalArtifactError("JSON object keys must be strings")
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise CanonicalArtifactError(f"NFC key collision: {normalized_key}")
            normalized[normalized_key] = normalize_nfc(item)
        return normalized
    raise CanonicalArtifactError(f"unsupported JSON value type: {type(value).__name__}")


def canonical_bytes(document: Any) -> bytes:
    try:
        return rfc8785.dumps(normalize_nfc(document))
    except rfc8785.CanonicalizationError as exc:
        raise CanonicalArtifactError(str(exc)) from exc


def canonical_sha256(document: Any) -> str:
    return hashlib.sha256(canonical_bytes(document)).hexdigest()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Hash P1 authority artifacts with NFC + RFC 8785 JCS")
    subparsers = result.add_subparsers(dest="action", required=True)
    for action in ("hash", "verify"):
        command = subparsers.add_parser(action)
        command.add_argument("--input", type=Path, required=True)
        if action == "verify":
            command.add_argument("--sha256", required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        digest = canonical_sha256(load_json(args.input.resolve()))
        if args.action == "verify" and digest != args.sha256:
            print(json.dumps({"status": "mismatch", "canonicalization_version": CANONICALIZATION_VERSION, "actual_sha256": digest}))
            return 4
        print(json.dumps({"status": "ok", "canonicalization_version": CANONICALIZATION_VERSION, "sha256": digest}))
        return 0
    except CanonicalArtifactError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
