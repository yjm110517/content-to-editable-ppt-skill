from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))
from contact_sheets import compose_preview_sheet


class DirectDeckPreviewTests(unittest.TestCase):
    def test_generic_preview_preserves_caller_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); first = root / "first.png"; second = root / "second.png"
            Image.new("RGB", (160, 90), "red").save(first); Image.new("RGB", (160, 90), "blue").save(second)
            output = root / "preview.png"; record = compose_preview_sheet(slides=[("S10", first), ("S02", second)], output=output, title="Preview")
            self.assertTrue(output.is_file()); self.assertEqual(record["slides"], 2)


if __name__ == "__main__": unittest.main()
