from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from canonical_artifact import canonical_sha256
from rebind_style_anchor import rebind
from schema_utils import ContractError


H = "a" * 64


def package(*, version: str, p2_hash: str, reused: bool) -> dict:
    return {
        "schema_version": version, "artifact_type": "deck_prompt_package", "deck_id": "D01",
        "deck_visual_system_sha256": H, "text_footprint_manifest_sha256": H,
        "deck_request_sha256": H, "approved_outline_sha256": H,
        "slide_content_manifest_sha256": H, "p2_manifest_sha256": p2_hash,
        "p3_icon_asset_index_sha256": H,
        "generation_policy": {"provider_policy":"runtime_default","model_policy":"runtime_default","initial_generation_limit":1,"technical_retry_limit":2},
        "shared_prompt": "shared", "negative_prompt": "negative", "style_anchor_slide_id": "S03", "high_risk_slide_ids": [],
        "slides": [{"slide_id":"S03","order":3,"role":"content","template_family":"content","prompt_input_sha256":H,"prompt_sha256":H,"prompt":"same prompt","element_intents":[{"source_ref":"S03-TITLE","element_owner":"deterministic_compositor","render_policy":"formal_text_overlay","footprint_ref":"S03:S03-TITLE","future_element_map_id":"EL-S03-TITLE"}],"reused":reused}],
        "status": "compiled",
    }


class StoryboardAnchorRebindTests(unittest.TestCase):
    def fixture(self, root: Path) -> argparse.Namespace:
        image = root / "layer.png"; image.write_bytes(b"layer")
        preview_image = root / "preview.png"; preview_image.write_bytes(b"preview")
        layer_sha = hashlib.sha256(b"layer").hexdigest(); preview_sha = hashlib.sha256(b"preview").hexdigest()
        old, new = package(version="1.0", p2_hash="b"*64, reused=False), package(version="1.1", p2_hash="c"*64, reused=True)
        layer = {"schema_version":"1.0","artifact_type":"generated_visual_layer_record","deck_id":"D01","slide_id":"S03","revision":1,"prompt_sha256":H,"runtime_lock_sha256":H,"source_image_sha256":layer_sha,"source_width_px":1600,"source_height_px":900,"image_path":"layer.png","image_sha256":layer_sha,"width_px":1600,"height_px":900,"normalization":"none","generation_kind":"initial","technical_retry_count":0,"status":"consumed"}
        mapping = {"schema_version":"1.0","artifact_type":"design_element_map","deck_id":"D01","slide_id":"S03","generated_layer_sha256":layer_sha,"prompt_package_sha256":canonical_sha256(old),"elements":[{"element_id":"EL-S03-TITLE","source_ref":"S03-TITLE","element_owner":"deterministic_compositor","reconstruction_class":"native_text","editable_required":True,"fidelity_priority":"critical","p4_strategy":"reuse_authority_text_spec","normalized_bbox":{"x":100,"y":100,"w":1000,"h":500},"z_index":1,"relationship_refs":[]}],"forbidden_generated_content":{"text_like_marks":False,"logo_like_marks":False,"unauthorized_labels":False,"duplicate_resolved_icons":False,"duplicate_chart_content":False,"unclassified_major_visual_count":0},"full_raw_layer_reuse_allowed":False,"host_map_pass_count":1,"map_correction_count":0,"status":"submitted"}
        preview = {"schema_version":"1.0","artifact_type":"final_design_preview_record","deck_id":"D01","slide_id":"S03","revision":1,"generated_layer_sha256":layer_sha,"element_map_sha256":canonical_sha256(mapping),"compatibility_report_sha256":H,"preview_build_report_sha256":H,"powerpoint_render_sha256":preview_sha,"final_preview_path":"preview.png","final_preview_sha256":preview_sha,"generated_layer_direct_approval":False,"status":"ready_for_confirmation"}
        feedback = {"schema_version":"1.0","artifact_type":"style_anchor_feedback","deck_id":"D01","slide_id":"S03","revision":1,"final_preview_sha256":preview_sha,"decision":"accepted","change_scope":"none","user_message_sha256":H}
        anchor = {"schema_version":"1.0","artifact_type":"style_anchor_record","deck_id":"D01","slide_id":"S03","revision":1,"final_preview_sha256":preview_sha,"generated_layer_sha256":layer_sha,"element_map_sha256":canonical_sha256(mapping),"deck_visual_system_sha256":H,"deck_prompt_package_sha256":canonical_sha256(old),"runtime_lock_sha256":H,"feedback_sha256":canonical_sha256(feedback),"status":"approved"}
        documents={"old":old,"new":new,"anchor":anchor,"layer":layer,"mapping":mapping,"preview":preview,"feedback":feedback};paths={}
        for name,document in documents.items():
            path=root/f"{name}.json";path.write_text(json.dumps(document),encoding="utf-8");paths[name]=path
        return argparse.Namespace(old_prompt_package=paths["old"],new_prompt_package=paths["new"],old_anchor_record=paths["anchor"],generated_layer_record=paths["layer"],generated_layer_image=image,element_map=paths["mapping"],final_preview_record=paths["preview"],final_preview_image=preview_image,feedback=paths["feedback"],compatibility_output=root/"compatibility.json",anchor_output=root/"rebound.json")

    def test_unchanged_reused_anchor_rebinds_to_new_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args=self.fixture(Path(temporary));result=rebind(args)
            rebound=json.loads(args.anchor_output.read_text())
            self.assertEqual(rebound["deck_prompt_package_sha256"],canonical_sha256(json.loads(args.new_prompt_package.read_text())))
            self.assertTrue(result["compatibility_record_sha256"])

    def test_changed_prompt_or_image_blocks_rebind_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            args=self.fixture(Path(temporary));new=json.loads(args.new_prompt_package.read_text());new["slides"][0]["prompt"]="changed";args.new_prompt_package.write_text(json.dumps(new))
            with self.assertRaises(ContractError):rebind(args)
            self.assertFalse(args.compatibility_output.exists());self.assertFalse(args.anchor_output.exists())


if __name__ == "__main__":
    unittest.main()
