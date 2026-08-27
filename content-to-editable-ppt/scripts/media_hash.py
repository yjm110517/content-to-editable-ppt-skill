from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decoded_rgb_sha256(path: Path) -> str:
    """Return a content hash independent of a PNG container's encoding details."""
    with Image.open(path) as image:
        image.load()
        pixels = image.convert("RGB").tobytes()
    return hashlib.sha256(pixels).hexdigest()
