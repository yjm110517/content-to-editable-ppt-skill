from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
SCHEMAS = ROOT / "content-to-editable-ppt" / "schemas"
import sys
sys.path.insert(0, str(SCRIPTS))

from canonical_artifact import canonical_sha256
from reconstruction_authority import build_reconstruction_asset_manifest, build_seed_view, load_reconstruction_authority
from reconstruction_state import initial_deck_state, initial_page_state, transition
from schema_utils import ContractError, validate_schema
from tests.runtime.test_p3_visual_system_contracts import visual_candidate

H = "a" * 64
NOW = "2026-08-18T00:00:00Z"


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def approved_content() -> dict:
    return {"schema_version":"1.0","canonicalization_version":"p1-rfc8785-nfc-1","artifact_id":"D01-S01-r1","deck_id":"D01","slide_id":"S01","order":1,"revision":1,"parent_sha256":None,"approved_outline_revision":1,"approved_outline_sha256":H,"confirmation_id":"confirm-1","projection":{"tool_version":"1.0","input_sha256":H,"output_content_sha256":H},"title":{"content_ref":"S01-TITLE","text":"重建标题"},"content_blocks":[{"content_ref":"S01-C01","order":1,"text":"重建正文","source_refs":["M01-F01"]}],"status":"frozen","frozen_at_utc":NOW}


def visual_system() -> dict:
    candidate = visual_candidate()
    return {"schema_version":"1.0","canonicalization_version":"p1-rfc8785-nfc-1","artifact_type":"deck_visual_system","deck_id":"D01","revision":1,"parent_sha256":None,"candidate_sha256":canonical_sha256(candidate),"deck_request_sha256":H,"approved_outline_sha256":H,"slide_content_manifest_sha256":H,"p2_manifest_sha256":H,"p3_icon_asset_index_sha256":H,"hard_constraints":candidate["hard_constraints"],"soft_design_guidance":candidate["soft_design_guidance"],"status":"frozen"}


def footprints(system: dict) -> dict:
    title = approved_content()["title"]["text"]
    body = approved_content()["content_blocks"][0]["text"]
    entries = []
    for ref, text, role, token, size, max_lines in (("S01-TITLE", title, "title", "title", 30, 2), ("S01-C01", body, "body", "body", 20, 5)):
        entries.append({"slide_id":"S01","content_ref":ref,"role":role,"text_sha256":hashlib.sha256(text.encode()).hexdigest(),"font_token":token,"font_family":"Microsoft YaHei","font_file_sha256":H,"font_size_pt":size,"line_height_milli":1200,"estimated_lines":1,"max_lines":max_lines,"preferred_width":4000,"min_height":1000,"safe_padding":250})
    return {"schema_version":"1.0","artifact_type":"text_footprint_manifest","deck_id":"D01","deck_visual_system_sha256":canonical_sha256(system),"slide_content_manifest_sha256":H,"algorithm":"pillow-10.4-96dpi-v1","font_environment_sha256":H,"entries":entries,"status":"pass"}


def element_map() -> dict:
    return {"schema_version":"1.0","artifact_type":"design_element_map","deck_id":"D01","slide_id":"S01","generated_layer_sha256":H,"prompt_package_sha256":H,"elements":[
        {"element_id":"GEN-S01-BG","source_ref":None,"element_owner":"generated_visual_layer","reconstruction_class":"generated_background","editable_required":False,"fidelity_priority":"major","p4_strategy":"rebuild_background_from_style_tokens","normalized_bbox":{"x":0,"y":0,"w":10000,"h":10000},"z_index":0,"relationship_refs":[]},
        {"element_id":"GEN-S01-CARD","source_ref":None,"element_owner":"generated_visual_layer","reconstruction_class":"native_shape","editable_required":True,"fidelity_priority":"major","p4_strategy":"rebuild_from_element_map","normalized_bbox":{"x":500,"y":1500,"w":4200,"h":3000},"z_index":5,"shape_kind":"rounded_rect","fill":"surface","border":"primary-soft","corner_radius":300,"opacity":1000,"shadow_class":"soft","relationship_refs":[]},
        {"element_id":"EL-S01-TITLE","source_ref":"S01-TITLE","element_owner":"deterministic_compositor","reconstruction_class":"native_text","editable_required":True,"fidelity_priority":"critical","p4_strategy":"reuse_authority_text_spec","normalized_bbox":{"x":500,"y":500,"w":5000,"h":1000},"z_index":20,"relationship_refs":[]},
        {"element_id":"EL-S01-C01","source_ref":"S01-C01","element_owner":"deterministic_compositor","reconstruction_class":"native_text","editable_required":True,"fidelity_priority":"critical","p4_strategy":"reuse_authority_text_spec","normalized_bbox":{"x":600,"y":1800,"w":3500,"h":1200},"z_index":20,"relationship_refs":["GEN-S01-CARD"]},
        {"element_id":"EL-S01-V01","source_ref":"S01-V01","element_owner":"generated_visual_layer","reconstruction_class":"reusable_raster","editable_required":False,"fidelity_priority":"major","p4_strategy":"extract_from_raw_layer","normalized_bbox":{"x":5200,"y":1800,"w":3500,"h":4500},"z_index":10,"relationship_refs":[]}
    ],"forbidden_generated_content":{"text_like_marks":False,"logo_like_marks":False,"unauthorized_labels":False,"duplicate_resolved_icons":False,"duplicate_chart_content":False,"unclassified_major_visual_count":0},"full_raw_layer_reuse_allowed":False,"host_map_pass_count":1,"map_correction_count":0,"status":"submitted"}


class ReconstructionContractTests(unittest.TestCase):
    def authority(self, root: Path) -> dict:
        page = root / "S01"; page.mkdir(parents=True)
        preview = page / "final-design-preview.png"; Image.new("RGB", (1600, 900), "white").save(preview)
        mapping = element_map(); write(page / "design-element-map.json", mapping)
        compat = {"schema_version":"1.0","artifact_type":"reconstruction_compatibility_report","deck_id":"D01","slide_id":"S01","element_map_sha256":canonical_sha256(mapping),"status":"pass","native_shape_count":1,"native_text_count":2,"native_chart_count":0,"sanitized_svg_count":0,"reusable_raster_count":1,"generated_foreground_count":0,"decorative_approximation_count":0,"unclassified_major_visual_count":0,"blocking_issues":[]}; write(page / "reconstruction-compatibility-report.json", compat)
        record = {"schema_version":"1.0","artifact_type":"final_design_preview_record","deck_id":"D01","slide_id":"S01","revision":1,"generated_layer_sha256":H,"element_map_sha256":canonical_sha256(mapping),"compatibility_report_sha256":canonical_sha256(compat),"preview_build_report_sha256":H,"powerpoint_render_sha256":sha(preview),"final_preview_path":"final-design-preview.png","final_preview_sha256":sha(preview),"generated_layer_direct_approval":False,"status":"ready_for_confirmation"}; write(page / "final-design-preview-record.json", record)
        manifest = {"schema_version":"1.0","artifact_type":"approved_design_preview_manifest","deck_id":"D01","style_anchor_sha256":H,"previews":[{"slide_id":"S01","order":1,"revision":1,"final_preview_record_sha256":canonical_sha256(record),"final_preview_sha256":sha(preview)}],"status":"approved"}; write(root / "approved.json", manifest)
        state = {"schema_version":"1.0","artifact_type":"design_preview_state","deck_id":"D01","state":"p3_3_complete","budgets":{"initial_generation_per_slide":1,"technical_retry_per_stage":2,"map_pass_per_page":1,"map_correction_per_page":1},"counters":{"image_generation_calls":1,"automatic_regeneration_count":0,"full_deck_redesign_count":0,"host_map_pass_count":1,"map_correction_count":0,"planner_calls":0},"current_artifacts":{"approved_design_preview_manifest_sha256":canonical_sha256(manifest)},"history":[]}; write(root / "p3-state.json", state)
        return load_reconstruction_authority(p3_state_path=root / "p3-state.json", approved_manifest_path=root / "approved.json", page_roots={"S01": page})

    def test_authority_closes_preview_map_and_compatibility_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); bundle = self.authority(root); self.assertEqual(bundle["deck_id"], "D01")
            preview = root / "S01" / "final-design-preview.png"; preview.write_bytes(preview.read_bytes() + b"tamper")
            with self.assertRaises(ContractError): load_reconstruction_authority(p3_state_path=root / "p3-state.json", approved_manifest_path=root / "approved.json", page_roots={"S01": root / "S01"})

    def test_asset_manifest_and_seed_view_are_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); bundle = self.authority(root); page = root / "S01"; asset = page / "visual.png"; Image.new("RGBA", (200, 200), (0, 0, 255, 255)).save(asset)
            record = {"schema_version":"1.0","artifact_type":"extracted_visual_asset_record","deck_id":"D01","slide_id":"S01","element_id":"EL-S01-V01","visual_ref":"S01-V01","approved_preview_sha256":bundle["pages"][0]["preview_record"]["final_preview_sha256"],"generated_layer_sha256":H,"element_map_sha256":canonical_sha256(bundle["pages"][0]["element_map"]),"crop_bbox":{"x":5200,"y":1800,"w":3500,"h":4500},"output_path":"visual.png","output_png_sha256":sha(asset),"background_removal_status":"clean_local_background","extraction_quality":"pass","status":"approved"}; write(page / "approved-extracted.json", record)
            manifest = build_reconstruction_asset_manifest(deck_id="D01", evidence_root=root, record_paths=[page / "approved-extracted.json"])
            system = visual_system(); view = build_seed_view(page=bundle["pages"][0], approved_content=approved_content(), visual_system=system, text_footprints=footprints(system), asset_manifest=manifest)
            self.assertEqual(view["status"], "complete"); self.assertEqual(len(view["seeds"]), 5); self.assertEqual(next(item for item in view["seeds"] if item["reconstruction_class"] == "native_shape")["implementation"]["shape_kind"], "rounded_rect")

    def test_incomplete_native_shape_returns_p3_3(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); bundle = self.authority(root); bundle["pages"][0]["element_map"]["elements"][1].pop("shadow_class")
            manifest = {"schema_version":"1.0","artifact_type":"reconstruction_asset_manifest","deck_id":"D01","evidence_root_sha256":H,"assets":[],"status":"validated"}; system = visual_system()
            with self.assertRaises(ContractError) as raised: build_seed_view(page=bundle["pages"][0], approved_content=approved_content(), visual_system=system, text_footprints=footprints(system), asset_manifest=manifest)
            self.assertIn("reconstruction_seed_incomplete", {item["code"] for item in raised.exception.errors})

    def test_states_enforce_fail_fast_budgets(self) -> None:
        deck = initial_deck_state("D01", H); deck = transition(deck, "reconstruction_preflight"); self.assertEqual(deck["state"], "reconstruction_preflight")
        page = initial_page_state("D01", "S01"); page = transition(page, "authority_validated"); page = transition(page, "seed_ready"); self.assertEqual(page["planner_calls"], 0)
        validate_schema("reconstruction_deck_state", deck, SCHEMAS); validate_schema("reconstruction_page_state", page, SCHEMAS)


if __name__ == "__main__": unittest.main()
