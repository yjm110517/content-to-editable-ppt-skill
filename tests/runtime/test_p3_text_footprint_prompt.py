from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[2];SCRIPTS=ROOT/"content-to-editable-ppt"/"scripts"
import sys
sys.path.insert(0,str(SCRIPTS))

from canonical_artifact import canonical_sha256
from schema_utils import ContractError
from visual_system_authority import build_validation_report, freeze_visual_system
from visual_system_prompt import apply_correction, compile_prompt_package, compile_text_footprints
from tests.runtime import test_p3_visual_system_contracts as contracts


class TextFootprintPromptTests(unittest.TestCase):
    @patch.dict(os.environ,{"IVT_AVAILABLE_FONTS":"Microsoft YaHei;Arial"})
    def test_footprint_is_deterministic_and_uses_actual_font_hash(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle,_=contracts.VisualSystemContractTests().authority(Path(temporary));system=freeze_visual_system(contracts.visual_candidate(),bundle)
            first=compile_text_footprints(system,bundle);second=compile_text_footprints(system,bundle)
            self.assertEqual(first,second);self.assertEqual([item["role"] for item in first["entries"]],["title","body"]);self.assertTrue(all(item["font_file_sha256"] for item in first["entries"]))

    @patch.dict(os.environ,{"IVT_AVAILABLE_FONTS":"Microsoft YaHei;Arial"})
    def test_unfit_text_is_blocking(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle,_=contracts.VisualSystemContractTests().authority(Path(temporary));bundle["slide_contents"]["S01"]["title"]["text"]="超长标题"*1000;system=freeze_visual_system(contracts.visual_candidate(),bundle)
            with self.assertRaises(ContractError) as raised:compile_text_footprints(system,bundle)
            self.assertIn("text_footprint_blocking",{item["code"] for item in raised.exception.errors})

    @patch.dict(os.environ,{"IVT_AVAILABLE_FONTS":"Microsoft YaHei;Arial"})
    def test_prompt_layer_ownership_and_raster_extractability(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle,_=contracts.VisualSystemContractTests().authority(Path(temporary));system=freeze_visual_system(contracts.visual_candidate(),bundle);foot=compile_text_footprints(system,bundle);first,anchor=compile_prompt_package(system,foot,bundle);second,_=compile_prompt_package(system,foot,bundle)
            self.assertEqual(first,second);slide=first["slides"][0];intents={item["source_ref"]:item for item in slide["element_intents"]}
            self.assertEqual(intents["S01-TITLE"]["element_owner"],"deterministic_compositor");self.assertEqual(intents["S01-V01"]["render_policy"],"generated_extraction_candidate")
            self.assertIn("minimum_short_edge=800",slide["prompt"]);self.assertIn("Generated Visual Layer is not the Final or Approved Design Preview",first["shared_prompt"]);self.assertEqual(anchor["status"],"ready_for_generation")

    @patch.dict(os.environ,{"IVT_AVAILABLE_FONTS":"Microsoft YaHei;Arial"})
    def test_prompt_cache_reuses_unchanged_page(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle,_=contracts.VisualSystemContractTests().authority(Path(temporary));system=freeze_visual_system(contracts.visual_candidate(),bundle);foot=compile_text_footprints(system,bundle);first,_=compile_prompt_package(system,foot,bundle);second,_=compile_prompt_package(system,foot,bundle,first)
            self.assertFalse(first["slides"][0]["reused"]);self.assertTrue(second["slides"][0]["reused"]);self.assertEqual(first["slides"][0]["prompt_sha256"],second["slides"][0]["prompt_sha256"])

    @patch.dict(os.environ,{"IVT_AVAILABLE_FONTS":"Microsoft YaHei;Arial"})
    def test_issue_bound_correction_only(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle,_=contracts.VisualSystemContractTests().authority(Path(temporary));candidate=contracts.visual_candidate();candidate["hard_constraints"]["safe_area"]["top"]=3000;report=build_validation_report(candidate,bundle,report_id="R",validated_at_utc=contracts.NOW);issue=next(item for item in report["issues"] if item["code"]=="safe_area_too_large")
            correction={"schema_version":"1.0","artifact_type":"deck_visual_system_correction_record","correction_id":"C1","deck_id":"D01","attempt":1,"host_model_invocation_id":"host-2","candidate_sha256":canonical_sha256(candidate),"validation_report_sha256":canonical_sha256(report),"operations":[{"op":"replace","validation_issue_id":issue["issue_id"],"path":"/hard_constraints/safe_area/top","before":3000,"after":500}],"created_at_utc":contracts.NOW}
            fixed=apply_correction(candidate,report,correction);self.assertEqual(fixed["hard_constraints"]["safe_area"]["top"],500)
            bad=copy.deepcopy(correction);bad["operations"][0]["validation_issue_id"]="OTHER"
            with self.assertRaises(ContractError):apply_correction(candidate,report,bad)

    @patch.dict(os.environ,{"IVT_AVAILABLE_FONTS":"Microsoft YaHei;Arial"})
    def test_cli_full_workflow_and_verify(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);_,paths=contracts.VisualSystemContractTests().authority(root);candidate_path=root/"visual-candidate.json";candidate_path.write_text(json.dumps(contracts.visual_candidate(),ensure_ascii=False,indent=2),encoding="utf-8")
            state=root/"p3-2-state.json";report=root/"report.json";system=root/"deck-visual-system.json";foot=root/"text-footprint-manifest.json";package=root/"deck-prompt-package.json";anchor=root/"style-anchor-request.json"
            common=["--p1-state",str(paths["p1_state"]),"--deck-request",str(paths["request"]),"--approved-outline",str(paths["outline"]),"--slide-content-dir",str(paths["content"]),"--p2-state",str(paths["p2_state"]),"--wireframe-root",str(paths["wireframes"]),"--icon-asset-index",str(paths["index"])]
            script=str(SCRIPTS/"manage_visual_system.py")
            commands=[
                ["init",*common,"--task-id","task-1","--state",str(state)],
                ["submit-candidate",*common,"--state",str(state),"--candidate",str(candidate_path),"--validation-report",str(report)],
                ["freeze",*common,"--state",str(state),"--candidate",str(candidate_path),"--output",str(system)],
                ["compile-footprints",*common,"--state",str(state),"--visual-system",str(system),"--output",str(foot)],
                ["compile-prompts",*common,"--state",str(state),"--visual-system",str(system),"--footprints",str(foot),"--package-output",str(package),"--anchor-output",str(anchor)],
                ["verify","--state",str(state),"--visual-system",str(system),"--footprints",str(foot),"--prompt-package",str(package),"--anchor-request",str(anchor)],
            ]
            for command in commands:
                completed=subprocess.run([sys.executable,script,*command],capture_output=True,text=True,env={**os.environ,"IVT_AVAILABLE_FONTS":"Microsoft YaHei;Arial"})
                self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
            self.assertEqual(json.loads(state.read_text())["state"],"p3_2_complete")


if __name__=="__main__":unittest.main()
