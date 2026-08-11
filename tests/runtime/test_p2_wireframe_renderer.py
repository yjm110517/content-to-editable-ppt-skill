from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from render_wireframe import audit_svg, canonical_number, render_document
from wireframe_rules import expected_authority
from tests.runtime.test_p2_wireframe_rules import approved, content, page, requirements, spec


class P2WireframeRendererTests(unittest.TestCase):
    def test_canonical_numeric_serialization(self) -> None:
        self.assertEqual(canonical_number(Decimal("533.280")), "533.28")
        self.assertEqual(canonical_number(Decimal("500.000")), "500")
        self.assertEqual(canonical_number(Decimal("-0.0001")), "0")
        self.assertEqual(canonical_number(Decimal("1.2345")), "1.234")

    def test_render_is_byte_for_byte_deterministic(self) -> None:
        document, authority = spec(), content()
        first, warnings_first = render_document(document, authority)
        second, warnings_second = render_document(document, authority)
        self.assertEqual(first, second)
        self.assertEqual(warnings_first, warnings_second)
        self.assertIn(b'viewBox="0 0 1600 900"', first)
        self.assertEqual(audit_svg(first, spec=document, slide_content=authority)["content_refs"], 2)

    def test_long_text_is_truncated_without_authority_drift(self) -> None:
        authority = content()
        authority["content_blocks"][0]["text"] = "很长的权威正文" * 100
        document = spec()
        document["authority"] = expected_authority(approved_outline=approved(), slide_content=authority, page=page(), layout_requirements=requirements(), output_ratio="16:9")
        rendered, warnings = render_document(document, authority)
        self.assertTrue(any(item["code"] == "preview_text_truncated" for item in warnings))
        self.assertIn(b'data-preview-display="truncated"', rendered)
        self.assertEqual(audit_svg(rendered, spec=document, slide_content=authority)["content_refs"], 2)

    def test_four_by_three_viewbox(self) -> None:
        document, authority = spec(), content()
        document["output_ratio"] = "4:3"
        document["authority"] = expected_authority(approved_outline=approved(), slide_content=authority, page=page(), layout_requirements=requirements(), output_ratio="4:3")
        rendered, _ = render_document(document, authority)
        self.assertIn(b'viewBox="0 0 1200 900"', rendered)


if __name__ == "__main__":
    unittest.main()
