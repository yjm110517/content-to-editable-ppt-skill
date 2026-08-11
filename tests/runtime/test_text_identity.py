from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from text_identity import TextIdentityError, build_compatibility_map, canonical_text, compare_authority, compatibility_view, layout_with_ppt_text


class TextIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.authority = {"text_items": [{"id": "title", "text": "知识\r\n整合"}]}
        self.layout = {"schema_version": "1.3", "elements": [{"id": "heading", "type": "text", "text": "知识\n整合"}]}

    def test_canonical_text_preserves_semantics(self) -> None:
        self.assertEqual(canonical_text("A\r\nB"), "A\nB")
        self.assertNotEqual(canonical_text("知识整合"), canonical_text("知识融合"))

    def test_unique_text_creates_read_only_view(self) -> None:
        original = copy.deepcopy(self.layout)
        mapping = build_compatibility_map(self.layout, self.authority)
        view = compatibility_view(self.layout, mapping)
        self.assertEqual(self.layout, original)
        self.assertEqual(view["schema_version"], "1.4")
        self.assertEqual(view["elements"][0]["content_ref"], "title")
        self.assertEqual(compare_authority(self.authority, view)["status"], "pass")

    def test_missing_authority_is_not_invented(self) -> None:
        mapping = build_compatibility_map({"schema_version": "1.3", "elements": []}, self.authority)
        self.assertEqual(mapping["unresolved"][0]["reason"], "missing")
        with self.assertRaises(TextIdentityError):
            compatibility_view(self.layout, mapping)

    def test_ambiguous_text_requires_explicit_mapping(self) -> None:
        layout = {"schema_version": "1.3", "elements": [
            {"id": "a", "type": "text", "text": "same"},
            {"id": "b", "type": "text", "text": "same"},
        ]}
        authority = {"text_items": [{"id": "source", "text": "same"}]}
        mapping = build_compatibility_map(layout, authority)
        self.assertEqual(mapping["unresolved"][0]["reason"], "ambiguous")

    def test_duplicate_or_non_contiguous_segments_fail(self) -> None:
        layout = {"elements": [
            {"id": "a", "type": "text", "text": "知", "content_ref": "title", "segment_order": 1, "joiner": ""},
            {"id": "b", "type": "text", "text": "识", "content_ref": "title", "segment_order": 1, "joiner": ""},
        ]}
        report = compare_authority({"text_items": [{"id": "title", "text": "知识"}]}, layout)
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["duplicate_segment_orders"], ["title"])
        self.assertEqual(report["non_contiguous_segment_orders"], ["title"])

    def test_runs_preserve_explicit_hard_line_break(self) -> None:
        layout = {"elements": [{
            "id": "a", "type": "text", "runs": [{"text": "A", "break_line": True}, {"text": "B"}],
            "content_ref": "title", "segment_order": 0, "joiner": "",
        }]}
        report = compare_authority({"text_items": [{"id": "title", "text": "A\nB"}]}, layout)
        self.assertEqual(report["status"], "pass")

    def test_ppt_text_is_extracted_by_layout_element_identity(self) -> None:
        case = ROOT / "baseline" / "cases" / "B06"
        report = __import__("json").loads((case / "case-report.json").read_text(encoding="utf-8"))
        frozen = case / "evidence" / "iterations" / f"{report['final_iteration']:02d}"
        layout = __import__("json").loads((frozen / "layout.json").read_text(encoding="utf-8"))
        authority = __import__("json").loads((case / "evidence" / "baseline-source-content.json").read_text(encoding="utf-8"))
        view = compatibility_view(layout, build_compatibility_map(layout, authority))
        extracted = layout_with_ppt_text(view, case / "evidence" / "final" / "baseline-final.pptx")
        self.assertEqual(compare_authority(authority, extracted)["status"], "pass")


if __name__ == "__main__":
    unittest.main()
