from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from canonical_artifact import canonical_sha256
from deterministic_project_slide_content import build_projection
from schema_utils import ContractError
from wireframe_rules import apply_correction, build_manifest, candidate_manifest_digest, expected_authority, layout_constraints_payload, load_authority_bundle, validate_spec, validation_report


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
    def authority_bundle(self, root: Path) -> dict[str, Path]:
        outline = approved()
        deck_request = {
            "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1",
            "task_id": "t", "deck_id": "D", "topic": "P2", "objective": "test authority",
            "audience": "developers", "language": "en", "page_count": 1, "output_ratio": "16:9",
            "source_material_ids": ["M01"], "must_preserve": [], "prohibited_changes": [],
            "visual_requirements": [], "external_research": "not_authorized",
        }
        layout = requirements()
        layout["deck_request_sha256"] = canonical_sha256(deck_request)
        slides, projection = build_projection(outline, frozen_at_utc=NOW)
        state = {
            "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1",
            "task_id": "t", "deck_id": "D", "state": "p1_complete",
            "counters": {"host_planning_pass_count": 1, "host_revision_pass_count": 0,
                         "automatic_regeneration_count": 0, "planner_calls": 0, "reviewer_calls": 0},
            "current_artifacts": {
                "task_route_sha256": None, "materials_sha256": None, "candidate_outline_sha256": None,
                "confirmation_sha256": None, "approved_outline_sha256": canonical_sha256(outline),
                "slide_content_manifest_sha256": canonical_sha256(projection),
            },
            "history": [],
        }
        paths = {
            "state": root / "state.json", "deck_request": root / "deck-request.json",
            "approved_outline": root / "approved-outline.json", "layout": root / "layout.json",
            "slide_content_dir": root / "slide-content",
        }
        paths["slide_content_dir"].mkdir()
        for path, document in ((paths["state"], state), (paths["deck_request"], deck_request),
                               (paths["approved_outline"], outline), (paths["layout"], layout)):
            path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        for slide, item in zip(slides, projection["slides"]):
            (paths["slide_content_dir"] / item["path"]).write_text(
                json.dumps(slide, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        (paths["slide_content_dir"] / "projection-manifest.json").write_text(
            json.dumps(projection, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return paths

    def load_bundle(self, paths: dict[str, Path]) -> dict:
        return load_authority_bundle(
            p1_state_path=paths["state"], deck_request_path=paths["deck_request"],
            approved_outline_path=paths["approved_outline"], slide_content_dir=paths["slide_content_dir"],
            layout_requirements_path=paths["layout"],
        )

    def mutate_json(self, path: Path, mutation) -> None:
        document = json.loads(path.read_text(encoding="utf-8"))
        mutation(document)
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

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

    def test_changed_scope_forces_rebuild_and_ratio_change_invalidates_page(self) -> None:
        document = spec()
        first = build_manifest(approved_outline=approved(), slide_content_manifest_sha256=H, specs=[document], layout_requirements=requirements(), output_ratio="16:9", artifact_id="m1", revision=1, created_at_utc=NOW)
        scoped = build_manifest(approved_outline=approved(), slide_content_manifest_sha256=H, specs=[document], layout_requirements=requirements(), output_ratio="16:9", artifact_id="m2", revision=2, previous_manifest=first, changed_slide_ids={"S01"}, created_at_utc=NOW)
        self.assertEqual(scoped["slides"][0]["build_status"], "rebuilt")

        changed_ratio = copy.deepcopy(document)
        changed_ratio["output_ratio"] = "4:3"
        changed_ratio["authority"] = expected_authority(approved_outline=approved(), slide_content=content(), page=page(), layout_requirements=requirements(), output_ratio="4:3")
        ratio_manifest = build_manifest(approved_outline=approved(), slide_content_manifest_sha256=H, specs=[changed_ratio], layout_requirements=requirements(), output_ratio="4:3", artifact_id="m3", revision=2, previous_manifest=first, created_at_utc=NOW)
        self.assertEqual(ratio_manifest["slides"][0]["build_status"], "rebuilt")

    def test_manifest_rejects_spec_with_mismatched_ratio(self) -> None:
        with self.assertRaises(ContractError):
            build_manifest(approved_outline=approved(), slide_content_manifest_sha256=H, specs=[spec()], layout_requirements=requirements(), output_ratio="4:3", artifact_id="m", revision=1, created_at_utc=NOW)

    def test_correction_cannot_replace_a_legal_semantic_reference(self) -> None:
        document = spec()
        report = validation_report(deck_id="D", candidate_sha256=candidate_manifest_digest([document]), issues=[{"issue_id": "i1", "slide_id": "S01", "classification": "correctable_contract_error", "code": "bbox_out_of_bounds", "path": "$.regions", "message": "bad box", "correctable": True}], report_id="r", validated_at_utc=NOW)
        correction = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "correction_id": "c", "deck_id": "D", "pass_id": "p", "attempt": 1, "host_model_invocation_id": "h2", "candidate_manifest_sha256": candidate_manifest_digest([document]), "validation_report_sha256": canonical_sha256(report), "operations": [{"validation_issue_id": "i1", "slide_id": "S01", "target_type": "region", "target_id": "chart", "field": "semantic_source_refs", "before": ["S01-C01"], "after": ["S01-TITLE"]}], "created_at_utc": NOW}
        with self.assertRaises(ContractError):
            apply_correction(specs=[document], report=report, correction=correction)

    def test_authority_bundle_binds_p1_state_to_frozen_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.authority_bundle(Path(temporary))
            bundle = self.load_bundle(paths)
            self.assertEqual(bundle["p1_state"]["state"], "p1_complete")

    def test_authority_bundle_rejects_outline_state_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.authority_bundle(Path(temporary))
            self.mutate_json(paths["state"], lambda value: value["current_artifacts"].update(approved_outline_sha256="0" * 64))
            with self.assertRaises(ContractError) as caught:
                self.load_bundle(paths)
            self.assertIn("authority_hash_mismatch", {item["code"] for item in caught.exception.errors})

    def test_authority_bundle_rejects_manifest_state_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.authority_bundle(Path(temporary))
            self.mutate_json(paths["state"], lambda value: value["current_artifacts"].update(slide_content_manifest_sha256="0" * 64))
            with self.assertRaises(ContractError) as caught:
                self.load_bundle(paths)
            self.assertIn("authority_hash_mismatch", {item["code"] for item in caught.exception.errors})

    def test_authority_bundle_rejects_missing_frozen_hashes(self) -> None:
        for field in ("approved_outline_sha256", "slide_content_manifest_sha256"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                paths = self.authority_bundle(Path(temporary))
                self.mutate_json(paths["state"], lambda value, key=field: value["current_artifacts"].update({key: None}))
                with self.assertRaises(ContractError) as caught:
                    self.load_bundle(paths)
                matching = [item for item in caught.exception.errors if item["path"].endswith(field)]
                self.assertEqual([item["code"] for item in matching], ["missing_authority"])

    def test_authority_bundle_rejects_invalid_empty_hashes_at_schema_gate(self) -> None:
        for field in ("approved_outline_sha256", "slide_content_manifest_sha256"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                paths = self.authority_bundle(Path(temporary))
                self.mutate_json(paths["state"], lambda value, key=field: value["current_artifacts"].update({key: ""}))
                with self.assertRaises(ContractError) as caught:
                    self.load_bundle(paths)
                self.assertIn("schema_error", {item["code"] for item in caught.exception.errors})

    def test_authority_bundle_rejects_artifact_tampering_with_stale_state_hash(self) -> None:
        for artifact in ("approved_outline", "projection_manifest"):
            with self.subTest(artifact=artifact), tempfile.TemporaryDirectory() as temporary:
                paths = self.authority_bundle(Path(temporary))
                target = paths["approved_outline"] if artifact == "approved_outline" else paths["slide_content_dir"] / "projection-manifest.json"
                self.mutate_json(target, lambda value: value.update(revision=2))
                with self.assertRaises(ContractError) as caught:
                    self.load_bundle(paths)
                self.assertIn("authority_hash_mismatch", {item["code"] for item in caught.exception.errors})

    def test_authority_bundle_classifies_unreadable_projection_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.authority_bundle(Path(temporary))
            (paths["slide_content_dir"] / "projection-manifest.json").write_text("{", encoding="utf-8")
            with self.assertRaises(ContractError) as caught:
                self.load_bundle(paths)
            matching = [item for item in caught.exception.errors if item["path"] == "$.slide_content_manifest"]
            self.assertEqual([item["code"] for item in matching], ["missing_authority"])


if __name__ == "__main__":
    unittest.main()
