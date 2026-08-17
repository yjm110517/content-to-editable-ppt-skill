from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
import sys
sys.path.insert(0, str(SCRIPTS))

from canonical_artifact import canonical_sha256
from markdown_wireframe import bind_markdown
from schema_utils import ContractError, validate_schema
from visual_system_authority import build_validation_report, freeze_visual_system, load_visual_system_authority, validate_icon_asset_index
from visual_system_state import VisualSystemStateError, initial_state, record_host_pass, transition
from wireframe_state import initial_state as p2_initial_state
from tests.runtime import test_p2_markdown_binder as p2tests

NOW = p2tests.NOW
candidate = p2tests.candidate


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def visual_candidate() -> dict:
    font = {"family":"Microsoft YaHei","fallback_family":"Arial","size_pt":20,"minimum_size_pt":16,"weight":"regular","max_lines":5,"line_height_milli":1200}
    return {
        "schema_version":"1.0","canonicalization_version":"p1-rfc8785-nfc-1","artifact_type":"deck_visual_system_candidate","artifact_id":"D01-visual-r1","deck_id":"D01","revision":1,"parent_sha256":None,"pass_id":"initial","host_model_invocation_id":"host-p32-1",
        "hard_constraints":{"output_ratio":"16:9","canvas":{"width_px":1600,"height_px":900},"safe_area":{"top":500,"right":500,"bottom":500,"left":500},"palette":{"primary":"#2457C5","background":"#FFFFFF","surface":"#F2F5FA","accent":"#F28C28","text_primary":"#111111","text_secondary":"#555555"},"typography":{"title":{**font,"size_pt":30,"minimum_size_pt":24,"weight":"bold","max_lines":2},"subtitle":{**font,"size_pt":24,"minimum_size_pt":20,"weight":"semibold","max_lines":2},"body":font,"label":{**font,"size_pt":16,"minimum_size_pt":12,"max_lines":2}},"prohibitions":{"model_rendered_formal_text":True,"model_redrawn_resolved_svg":True,"logos":True,"watermarks":True,"external_assets":True,"extra_facts":True,"full_slide_text_rasterization":True},"raster_handoff_policy":{"must_be_spatially_isolated":True,"must_not_contain_text":True,"must_not_be_occluded":True,"minimum_short_edge":800,"safe_padding":300,"avoid_background_entanglement":True,"avoid_long_range_shadow":True}},
        "soft_design_guidance":{"style_concept":"现代教育科技视觉，保持清晰层级和自由构图。","style_keywords":["modern","educational","confident"],"grid":{"recommended_columns":6,"recommended_gutter":300},"spacing_scale":[200,300,500,800],"template_families":[{"slide_role":"content","family":"content"}],"card_language":"轻量表面和克制阴影，可按页面构图自由使用。","image_treatment":"主体清晰，可使用非对称裁切。","chart_treatment":"保持数据区域简洁，正式数字后续叠加。","diagram_treatment":"强调关系和阅读方向，不绘制正式标签。","composition_guidance":["允许非对称构图","保留明显视觉焦点"],"creative_freedom":{"asymmetry":True,"scale_contrast":True,"local_overlap":True,"image_text_interplay":True,"irregular_rhythm":True}},
        "created_at_utc":NOW,
    }


class VisualSystemContractTests(unittest.TestCase):
    def authority(self, root: Path) -> tuple[dict, dict[str, Path]]:
        helper = p2tests.MarkdownWireframeBinderTests()
        p1_paths = helper.authority_paths(root)
        p1_bundle = helper.bundle(root / "other") if False else None
        from markdown_wireframe import load_markdown_authority
        p1_bundle = load_markdown_authority(p1_state_path=p1_paths["state"], approved_outline_path=p1_paths["outline"], slide_content_dir=p1_paths["content"])
        wf_candidate = candidate()
        markdown, manifest = bind_markdown(wf_candidate, p1_bundle)
        manifest["status"] = "accepted"
        wireframes = root / "wireframes"; revision = wireframes / "revisions" / "r001"; revision.mkdir(parents=True)
        (wireframes / "deck-wireframe.md").write_bytes(markdown); write(wireframes / "wireframe-manifest.json", manifest); write(revision / "candidate.json", wf_candidate)
        p2_state = p2_initial_state(task_id="task-1",deck_id="D01",approved_outline_sha256=manifest["approved_outline_sha256"],slide_content_manifest_sha256=manifest["slide_content_manifest_sha256"])
        p2_state["state"]="p2_complete"; p2_state["current_revision"]=1; p2_state["current_artifacts"]["candidate_sha256"]=manifest["candidate_sha256"]; p2_state["current_artifacts"]["wireframe_manifest_sha256"]=canonical_sha256(manifest); p2_state["current_artifacts"]["wireframe_sha256"]=manifest["wireframe_sha256"]
        p2_state_path=root/"p2-state.json"; write(p2_state_path,p2_state)
        request={"schema_version":"1.0","canonicalization_version":"p1-rfc8785-nfc-1","task_id":"task-1","deck_id":"D01","topic":"AI学习","objective":"解释支持方式","audience":"教师","language":"zh-CN","page_count":1,"output_ratio":"16:9","source_material_ids":["M01"],"must_preserve":[],"prohibited_changes":[],"visual_requirements":[],"external_research":"not_authorized"}
        request_path=root/"deck-request.json"; write(request_path,request)
        p2_sha=canonical_sha256(manifest)
        handoff={"schema_version":"1.0","artifact_type":"raster_handoff_pending","deck_id":"D01","slide_id":"S01","visual_ref":"S01-V01","semantic":"生成式AI","semantic_source_refs":["S01-TITLE"],"p2_manifest_sha256":p2_sha,"visual_direction_sha256":"a"*64,"search_evidence_sha256":"b"*64,"selection_decision_sha256":"c"*64,"reason":"no_accurate_tabler_match","status":"raster_handoff_pending","created_at_utc":NOW}
        handoff_path=root/"assets"/"S01-V01-handoff.json"; write(handoff_path,handoff)
        index={"schema_version":"1.0","canonicalization_version":"p1-rfc8785-nfc-1","artifact_type":"p3_icon_asset_authority_index","scope":"icon","deck_id":"D01","p2_manifest_sha256":p2_sha,"entries":[{"visual_ref":"S01-V01","status":"raster_handoff_pending","handoff_path":"assets/S01-V01-handoff.json","handoff_sha256":canonical_sha256(handoff)}]}
        index_path=root/"p3-icon-asset-authority-index.json"; write(index_path,index)
        paths={"p1_state":p1_paths["state"],"request":request_path,"outline":p1_paths["outline"],"content":p1_paths["content"],"p2_state":p2_state_path,"wireframes":wireframes,"index":index_path}
        bundle=load_visual_system_authority(p1_state_path=paths["p1_state"],deck_request_path=paths["request"],approved_outline_path=paths["outline"],slide_content_dir=paths["content"],p2_state_path=paths["p2_state"],wireframe_root=paths["wireframes"],icon_asset_index_path=paths["index"])
        return bundle,paths

    @patch.dict(os.environ,{"IVT_AVAILABLE_FONTS":"Microsoft YaHei;Arial"})
    def test_authority_candidate_and_freeze_close_hash_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle,_=self.authority(Path(temporary)); candidate_doc=visual_candidate()
            report=build_validation_report(candidate_doc,bundle,report_id="R1",validated_at_utc=NOW)
            self.assertEqual(report["status"],"pass")
            frozen=freeze_visual_system(candidate_doc,bundle)
            self.assertEqual(frozen["status"],"frozen"); self.assertEqual(frozen["p2_manifest_sha256"],bundle["hashes"]["p2_manifest_sha256"])

    def test_cross_deck_and_handoff_tampering_are_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); _,paths=self.authority(root); state=json.loads(paths["p2_state"].read_text()); state["deck_id"]="OTHER"; write(paths["p2_state"],state)
            with self.assertRaises(ContractError):
                load_visual_system_authority(p1_state_path=paths["p1_state"],deck_request_path=paths["request"],approved_outline_path=paths["outline"],slide_content_dir=paths["content"],p2_state_path=paths["p2_state"],wireframe_root=paths["wireframes"],icon_asset_index_path=paths["index"])
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); _,paths=self.authority(root); handoff=root/"assets"/"S01-V01-handoff.json"; handoff.write_bytes(handoff.read_bytes()+b" ")
            with self.assertRaises(ContractError): validate_icon_asset_index(paths["index"],json.loads((paths["wireframes"]/"wireframe-manifest.json").read_text()))

    @patch.dict(os.environ,{"IVT_AVAILABLE_FONTS":"Microsoft YaHei;Arial"})
    def test_hard_soft_semantics_and_role_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle,_=self.authority(Path(temporary)); bad=visual_candidate(); bad["soft_design_guidance"]["template_families"]=[]
            with self.assertRaises(ContractError): validate_schema("deck_visual_system_candidate",bad,ROOT/"content-to-editable-ppt"/"schemas")
            bad=visual_candidate(); bad["hard_constraints"]["safe_area"]["top"]=3000
            report=build_validation_report(bad,bundle,report_id="R2",validated_at_utc=NOW); self.assertIn("safe_area_too_large",{item["code"] for item in report["issues"]})

    def test_state_enforces_one_correction_and_zero_automatic_calls(self) -> None:
        state=initial_state("task-1","D01"); state=transition(state,"validating_authority"); state=transition(state,"authority_validated"); state=transition(state,"visual_system_planning")
        state=record_host_pass(state); state=record_host_pass(state,correction=True)
        with self.assertRaises(VisualSystemStateError): record_host_pass(state,correction=True)
        self.assertEqual(state["counters"]["host_model_invocation_count"],2); self.assertEqual(state["counters"]["automatic_visual_redesign_count"],0)

    def test_all_new_schemas_parse(self) -> None:
        schema_dir=ROOT/"content-to-editable-ppt"/"schemas"
        for path in schema_dir.glob("*.schema.json"):
            json.loads(path.read_text(encoding="utf-8"))


if __name__=="__main__": unittest.main()
