from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from schema_utils import ContractError
from render_wireframe import audit_svg, canonical_number, render_document
from wireframe_rules import expected_authority
from tests.runtime.test_p2_wireframe_rules import approved, content, page, requirements, spec


class P2WireframeRendererTests(unittest.TestCase):
    def assert_audit_error(self, rendered: bytes, document: dict, authority: dict, code: str) -> None:
        with self.assertRaises(ContractError) as raised:
            audit_svg(rendered, spec=document, slide_content=authority)
        self.assertIn(code, {item["code"] for item in raised.exception.errors})

    @staticmethod
    def tamper(rendered: bytes, ref: str, mutate) -> bytes:
        root = ET.fromstring(rendered)
        group = next(item for item in root.iter() if item.attrib.get("data-content-ref") == ref)
        mutate(group)
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

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

    def test_full_visible_text_tampering_is_rejected(self) -> None:
        document, authority = spec(), content()
        rendered, _ = render_document(document, authority)
        tampered = self.tamper(rendered, "S01-C01", lambda group: setattr(next(item for item in group.iter() if item.tag.endswith("tspan")), "text", "Bady"))
        self.assert_audit_error(tampered, document, authority, "svg_preview_text")

    def test_truncated_prefix_and_ellipsis_tampering_is_rejected(self) -> None:
        authority = content()
        authority["content_blocks"][0]["text"] = "Generative artificial intelligence " * 100
        document = spec()
        document["authority"] = expected_authority(approved_outline=approved(), slide_content=authority, page=page(), layout_requirements=requirements(), output_ratio="16:9")
        rendered, _ = render_document(document, authority)
        for replacement in ("Generative art…", "Generative artificial intelligence"):
            tampered = self.tamper(rendered, "S01-C01", lambda group, value=replacement: setattr(next(item for item in group.iter() if item.tag.endswith("tspan")), "text", value))
            self.assert_audit_error(tampered, document, authority, "svg_preview_text")

    def test_preview_mode_authority_hash_and_length_tampering_are_rejected(self) -> None:
        document, authority = spec(), content()
        rendered, _ = render_document(document, authority)
        cases = (
            (lambda group: group.set("data-preview-display", "truncated"), "svg_preview_text"),
            (lambda group: group.set("data-authority-sha256", "0" * 64), "svg_authority_hash"),
            (lambda group: group.set("data-authority-length", "999"), "svg_authority_length"),
        )
        for mutate, code in cases:
            with self.subTest(code=code):
                self.assert_audit_error(self.tamper(rendered, "S01-C01", mutate), document, authority, code)

    def test_content_ref_delete_replace_and_duplicate_are_rejected(self) -> None:
        document, authority = spec(), content()
        rendered, _ = render_document(document, authority)
        mutations = (
            lambda group: group.attrib.pop("data-content-ref"),
            lambda group: group.set("data-content-ref", "UNKNOWN"),
            lambda group: group.set("data-content-ref", "S01-TITLE"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.assert_audit_error(self.tamper(rendered, "S01-C01", mutate), document, authority, "svg_content_mapping")

    def test_tspan_missing_added_and_reordered_are_rejected(self) -> None:
        authority = content()
        authority["content_blocks"][0]["text"] = "第一行\n第二行"
        document = spec()
        document["authority"] = expected_authority(approved_outline=approved(), slide_content=authority, page=page(), layout_requirements=requirements(), output_ratio="16:9")
        rendered, _ = render_document(document, authority)

        def remove(group):
            text = next(item for item in group if item.tag.endswith("text"))
            text.remove(list(text)[0])

        def add(group):
            text = next(item for item in group if item.tag.endswith("text"))
            ET.SubElement(text, "tspan").text = "extra"

        def reorder(group):
            text = next(item for item in group if item.tag.endswith("text"))
            children = list(text)
            text.remove(children[0])
            text.append(children[0])

        for mutate in (remove, add, reorder):
            with self.subTest(mutate=mutate):
                self.assert_audit_error(self.tamper(rendered, "S01-C01", mutate), document, authority, "svg_preview_text")

    def test_active_external_and_local_content_are_rejected(self) -> None:
        document, authority = spec(), content()
        rendered, _ = render_document(document, authority)
        payloads = (
            rendered.replace(b"</svg>", b"<script>alert(1)</script></svg>"),
            rendered.replace(b"</svg>", b'<a href="https://example.com"/></svg>'),
            rendered.replace(b"</svg>", b'<path onclick="alert(1)"/></svg>'),
            rendered.replace(b"</svg>", b'<text>C:\\Users\\private</text></svg>'),
        )
        for payload in payloads:
            with self.subTest(payload=payload[-80:]):
                self.assert_audit_error(payload, document, authority, "unsafe_svg")

    def test_unicode_cjk_and_multiline_are_deterministic(self) -> None:
        authority = content()
        authority["content_blocks"][0]["text"] = "生成式 AI\n支持学习者反思与协作"
        document = spec()
        document["authority"] = expected_authority(approved_outline=approved(), slide_content=authority, page=page(), layout_requirements=requirements(), output_ratio="16:9")
        first, _ = render_document(document, authority)
        second, _ = render_document(document, authority)
        self.assertEqual(first, second)
        self.assertEqual(audit_svg(first, spec=document, slide_content=authority)["status"], "pass")

    def test_four_by_three_viewbox(self) -> None:
        document, authority = spec(), content()
        document["output_ratio"] = "4:3"
        document["authority"] = expected_authority(approved_outline=approved(), slide_content=authority, page=page(), layout_requirements=requirements(), output_ratio="4:3")
        rendered, _ = render_document(document, authority)
        self.assertIn(b'viewBox="0 0 1200 900"', rendered)


if __name__ == "__main__":
    unittest.main()
