from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from canonical_artifact import canonical_sha256
from schema_utils import ContractError
from wireframe_rules import apply_correction, build_manifest, candidate_manifest_digest, expected_authority, layout_constraints_payload, validate_spec, validation_report


H = "a" * 64
NOW = "2026-08-11T00:00:00Z"


def page(order: int = 1) -> dict:
    return {"slide_id": "S01", "order": order, "role": "content", "purpose": "explain", "key_message": "message", "title": {"content_ref": "S01-TITLE", "text": "Title"}, "content_blocks": [{"content_ref": "S01-C01", "order": 1, "text": "Body", "source_refs": ["M01-F01"]}], "visual_intent": "chart", "source_refs": ["M01-F01"]}


def approved(order: int = 1) -> dict:
    return {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "a1", "deck_id": "D", "revision": 1, "parent_sha256": None, "candidate_revision": 1, "candidate_sha256": H, "confirmation_id": "c", "confirmation_sha256": H, "pages": [page(order)], "approved_at_utc": NOW}


def content(order: int = 1) -> dict:
    p = page(order)
    return {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "s1", "deck_id": "D", "slide_id": "S01", "order": order, "revision": 1, "parent_sha256": None, "approved_outline_revision": 1, "approved_outline_sha256": H, "confirmation_id": "c", "projection": {"tool_version": "1.0", "input_sha256": H, "output_content_sha256": H}, "title": p["title"], "content_blocks": p["content_blocks"], "status": "frozen", "frozen_at_utc": NOW}


def requirements() -> dict:
    result = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "lr", "deck_id": "D", "deck_request_sha256": H, "revision": 1, "parent_sha256": None, "density": "balanced", "preferred_region_structure": ["modular"], "required_visual_zones": [{"scope": "S01", "role": "chart", "minimum_count": 1}], "layout_direction": "left_to_right", "reserved_areas": {"header_height": 0, "footer_height": 0}, "cross_slide_structural_consistency": "moderate", "layout_constraints_sha256": H, "source_classifications": [], "created_at_utc": NOW}
    result["layout_constraints_sha256"] = canonical_sha256(layout_constraints_payload(result))
    return result


def region(identifier: str, role: str, bbox: dict, refs: list[str], *, semantic: list[str] | None = None, parent: str | None = None, level: int = 1, z: int = 10, overlap: str | None = None) -> dict:
    return {"region_id": identifier, "role": role, "parent_region_id": parent, "bbox": bbox, "content_refs": refs, "semantic_source_refs": semantic or [], "hierarchy_level": level, "emphasis": "primary", "z_index": z, "overlap_group": overlap}


def spec(order: int = 1) -> dict:
    a, c, p, lr = approved(order), content(order), page(order), requirements()
    authority = expected_authority(approved_outline=a, slide_content=c, page=p, layout_requirements=lr, output_ratio="16:9")
    return {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "wf", "deck_id": "D", "slide_id": "S01", "revision": 1, "parent_sha256": None, "authority": authority, "coordinate_system": "normalized_10000", "output_ratio": "16:9", "layout_pattern": "chart_focus", "focal_region_id": "root", "regions": [
        region("root", "container", {"x": 500, "y": 500, "w": 9000, "h": 8500}, []),
        region("title", "title", {"x": 800, "y": 800, "w": 8400, "h": 1000}, ["S01-TITLE"], parent="root", level=2),
        region("body", "content", {"x": 800, "y": 2200, "w": 3500, "h": 5200}, ["S01-C01"], parent="root", level=2),
        region("chart", "chart", {"x": 4800, "y": 2200, "w": 4000, "h": 5200}, [], semantic=["S01-C01"], parent="root", level=2),
    ], "relationships": [{"relationship_id": "rel1", "kind": "association", "from_region_id": "body", "to_region_id": "chart", "direction": "forward"}], "created_at_utc": NOW}


class P2WireframeRulesTests(unittest.TestCase):
    def validate(self, document: dict, *, order: int = 1) -> list[dict]:
        return validate_spec(document, approved_outline=approved(order), slide_content=content(order), page=page(order), layout_requirements=requirements(), output_ratio="16:9")

    def test_valid_hierarchy_and_semantic_reference_pass(self) -> None:
        self.assertEqual(self.validate(spec()), [])

    def test_content_exactly_once_but_semantic_reference_can_repeat(self) -> None:
        document = spec()
        document["regions"][3]["semantic_source_refs"] = ["S01-C01"]
        self.assertEqual(self.validate(document), [])
        document["regions"][3]["content_refs"] = ["S01-C01"]
        self.assertIn("duplicate_content_ref", {item["code"] for item in self.validate(document)})

    def test_foreground_decoration_requires_overlay(self) -> None:
        document = spec()
        document["regions"].append(region("badge", "decoration", {"x": 700, "y": 700, "w": 1000, "h": 500}, [], parent="root", level=2, z=20))
        self.assertIn("foreground_decoration_requires_overlay", {item["code"] for item in self.validate(document)})
        document["relationships"].append({"relationship_id": "over1", "kind": "overlay", "from_region_id": "badge", "to_region_id": "title", "direction": "none"})
        self.assertNotIn("foreground_decoration_requires_overlay", {item["code"] for item in self.validate(document)})

    def test_order_only_change_reuses_page_spec(self) -> None:
        document = spec(order=1)
        first = build_manifest(approved_outline=approved(1), slide_content_manifest_sha256=H, specs=[document], layout_requirements=requirements(), output_ratio="16:9", artifact_id="m1", revision=1, created_at_utc=NOW)
        second = build_manifest(approved_outline=approved(2), slide_content_manifest_sha256=H, specs=[document], layout_requirements=requirements(), output_ratio="16:9", artifact_id="m2", revision=2, previous_manifest=first, created_at_utc=NOW)
        self.assertEqual(second["slides"][0]["order"], 2)
        self.assertEqual(second["slides"][0]["build_status"], "reused")
        self.assertEqual(first["slides"][0]["spec_sha256"], second["slides"][0]["spec_sha256"])

    def test_correction_cannot_replace_a_legal_semantic_reference(self) -> None:
        document = spec()
        report = validation_report(deck_id="D", candidate_sha256=candidate_manifest_digest([document]), issues=[{"issue_id": "i1", "slide_id": "S01", "classification": "correctable_contract_error", "code": "bbox_out_of_bounds", "path": "$.regions", "message": "bad box", "correctable": True}], report_id="r", validated_at_utc=NOW)
        correction = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "correction_id": "c", "deck_id": "D", "pass_id": "p", "attempt": 1, "host_model_invocation_id": "h2", "candidate_manifest_sha256": candidate_manifest_digest([document]), "validation_report_sha256": canonical_sha256(report), "operations": [{"validation_issue_id": "i1", "slide_id": "S01", "target_type": "region", "target_id": "chart", "field": "semantic_source_refs", "before": ["S01-C01"], "after": ["S01-TITLE"]}], "created_at_utc": NOW}
        with self.assertRaises(ContractError):
            apply_correction(specs=[document], report=report, correction=correction)


if __name__ == "__main__":
    unittest.main()
