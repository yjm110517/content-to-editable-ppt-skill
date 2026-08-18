from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_bytes
from schema_utils import ContractError, error


def p5_canonical_bytes(document: dict[str, Any]) -> bytes:
    """Strict RFC 8785 / JCS + NFC canonical serialization + trailing LF (No BOM)."""
    return canonical_bytes(document) + b"\n"


def _atomic_write(path: Path, content: bytes) -> None:
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_once_p5_artifact(path: Path, document: dict[str, Any]) -> bool:
    """Immutable artifact write: absent -> atomic create; identical bytes -> idempotent;
    different bytes -> overwrite_forbidden (old bytes preserved). Returns True when created."""
    payload = p5_canonical_bytes(document)
    if path.exists():
        existing = path.read_bytes()
        if existing == payload:
            return False
        raise ContractError([error(str(path), "immutable P5 artifact already exists with different bytes", "overwrite_forbidden")])
    _atomic_write(path, payload)
    return True


def atomic_replace_p5_state(path: Path, document: dict[str, Any]) -> None:
    """State file: atomic replace (validated next state by the caller before this call)."""
    _atomic_write(path, p5_canonical_bytes(document))
