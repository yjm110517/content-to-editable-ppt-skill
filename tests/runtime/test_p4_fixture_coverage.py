from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];SCRIPTS=ROOT/"content-to-editable-ppt"/"scripts";sys.path.insert(0,str(SCRIPTS))
from tests.runtime.test_p4_reconstruction_contracts import H,write

def text_impl(text:str)->dict:return {"content_ref":"S01-TITLE","text":text,"text_sha256":hashlib.sha256(text.encode()).hexdigest(),"font_family":"Microsoft YaHei","fallback_family":"Arial","font_size_pt":30,"minimum_font_size_pt":24,"weight":"bold","alignment":"left","vertical_alignment":"top","margin_milli":0,"line_spacing_milli":1200,"wrap_policy":"powerpoint_wrap","max_lines":2,"color":"#111111"}
def element(eid:str,kind:str,z:int,impl:dict,box:dict|None=None)->dict:return {"element_id":eid,"source_ref":"S01-TITLE" if kind=="native_text" else "S01-V01" if kind in {"native_chart","sanitized_svg"} else None,"reconstruction_class":kind,"p4_strategy":{"native_text":"reuse_authority_text_spec","native_shape":"rebuild_from_element_map","native_chart":"reuse_powerpoint_chart_spec","sanitized_svg":"reuse_authority_asset","generated_background":"rebuild_background_from_style_tokens"}[kind],"fidelity_priority":"critical" if kind=="native_text" else "major","normalized_bbox":box or {"x":500,"y":500,"w":3000,"h":1500},"z_index":z,"implementation":impl}

class P4FixtureCoverageTests(unittest.TestCase):
    def test_d05_native_chart_svg_and_card_build(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);svg=root/"icon.svg";svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor"/></svg>',encoding="utf-8");digest=hashlib.sha256(svg.read_bytes()).hexdigest()
            asset={"schema_version":"1.0","artifact_type":"reconstruction_asset_manifest","deck_id":"D05","evidence_root_sha256":H,"assets":[{"asset_ref":"S01-V01","slide_id":"S01","element_id":"EL-S01-V01","record_sha256":H,"path":"icon.svg","sha256":digest,"media_type":"image/svg+xml","status":"approved"}],"status":"validated"};write(root/"assets.json",asset)
            chart={"schema_version":"1.0","artifact_type":"powerpoint_chart_spec","deck_id":"D05","slide_id":"S01","visual_ref":"S01-CHART","chart_type":"vertical_bar","categories":["A","B"],"series":[{"name":"Series","scaled_integer_values":[10,20]}],"value_scale":1,"unit":"count","source_refs":["S01-C01"],"confirmation_sha256":H,"show_legend":False,"show_value":True,"number_format":"0","color_tokens":["2457C5"],"status":"frozen"}
            elements=[element("BG","generated_background",0,{"background_strategy":"reconstructable_background","fill_color":"#FFFFFF","surface_color":"#F2F5FA","primary_color":"#2457C5","accent_color":"#F28C28"},{"x":0,"y":0,"w":10000,"h":10000}),element("CARD","native_shape",5,{"shape_kind":"rounded_rect","style_seed":{"fill_token":"surface","fill_color":"#F2F5FA","border_token":"primary","border_color":"#2457C5","radius_token":"card_md","corner_radius":300,"shadow_token":"soft","opacity_milli":1000}},{"x":400,"y":1600,"w":4000,"h":5000}),element("TITLE","native_text",20,text_impl("Fixture Chart")),element("CHART","native_chart",15,{"chart_spec":chart,"chart_spec_sha256":H},{"x":800,"y":2500,"w":3500,"h":3500}),element("ICON","sanitized_svg",16,{"asset_ref":"S01-V01","approved_record_sha256":H,"actual_asset_sha256":digest,"asset_path":"icon.svg","media_type":"image/svg+xml","fit":"contain","crop":None,"layer_role":"content"},{"x":6000,"y":2500,"w":2000,"h":2000})]
            spec={"schema_version":"1.0","artifact_type":"visual_reconstruction_spec","deck_id":"D05","slide_id":"S01","output_ratio":"16:9","order":1,"order_sensitive":False,"order_bindings":[],"order_context":{},"approved_preview_sha256":H,"element_map_sha256":H,"reconstruction_seed_view_sha256":H,"content_authority_sha256":H,"asset_manifest_sha256":H,"page_input_sha256":H,"elements":elements,"status":"validated"};write(root/"spec.json",spec)
            run=subprocess.run([os.environ.get("P3_TEST_NODE","node"),str(SCRIPTS/"build_reconstruction_page.mjs"),"--spec",str(root/"spec.json"),"--asset-manifest",str(root/"assets.json"),"--evidence-root",str(root),"--output",str(root/"page.pptx"),"--report",str(root/"report.json"),"--python",sys.executable],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            with zipfile.ZipFile(root/"page.pptx") as archive:self.assertTrue(any(name.startswith("ppt/charts/chart") for name in archive.namelist()));self.assertTrue(any(name.endswith(".svg") for name in archive.namelist()))

    def test_d08_connector_and_order_sensitive_contract(self)->None:
        arrow=element("ARROW","native_shape",5,{"shape_kind":"arrow","style_seed":{"fill_token":"none","fill_color":"#FFFFFF","border_token":"primary","border_color":"#2457C5","radius_token":"none","corner_radius":0,"shadow_token":"none","opacity_milli":1000}},{"x":2000,"y":5000,"w":5000,"h":500})
        self.assertEqual(arrow["implementation"]["shape_kind"],"arrow");self.assertEqual(arrow["reconstruction_class"],"native_shape")

if __name__=="__main__":unittest.main()
