from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from style_anchor_workflow import _mask_compositor_regions  # noqa: E402


class StyleAnchorReferenceTests(unittest.TestCase):
    def test_text_mask_includes_safety_halo_without_changing_map_bbox(self) -> None:
        raw = Image.new("RGB", (100, 100), "white")
        final = raw.copy()
        ImageDraw.Draw(final).rectangle((8, 8, 21, 21), fill="black")
        mapping = {
            "elements": [{
                "element_id": "EL-S01-TITLE",
                "reconstruction_class": "native_text",
                "normalized_bbox": {"x": 1000, "y": 1000, "w": 1000, "h": 1000},
            }]
        }
        masked = _mask_compositor_regions(final, raw, mapping)
        self.assertEqual(masked, ["EL-S01-TITLE"])
        self.assertEqual(final.getpixel((8, 8)), (255, 255, 255))
        self.assertEqual(final.getpixel((21, 21)), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
