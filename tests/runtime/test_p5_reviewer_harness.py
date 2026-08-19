from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from agent_common import load_role
from p5_reviewer_evidence import validate_p5_reviewer_evidence
from schema_utils import ContractError


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def response() -> dict:
    return {"schema_version":"1.0","artifact_type":"deck_consistency_reviewer_response","deck_id":"D03","reviewer_recommendation":"pass","issues":[],"mandatory_checks":{"typography_consistent":True,"palette_consistent":True,"background_consistent":True,"card_language_consistent":True,"density_spacing_consistent":True,"visual_treatment_consistent":True,"navigation_consistent":True,"section_hierarchy_consistent":True,"same_deck_identity":True,"no_reopened_p4_fidelity":True},"structured_upstream_revision":None}


class P5ReviewerHarnessTests(unittest.TestCase):
    def prepare(self, root: Path) -> tuple[Path, Path]:
        inputs = root / "review-inputs"; inputs.mkdir()
        for name in ("approved-preview-contact-sheet.png","final-candidate-contact-sheet.png","approved-vs-final-comparison-sheet.png"):
            Image.new("RGB",(32,18),"white").save(inputs/name)
        for name in ("deck-visual-system-summary.json","deck-final-qa-report.json","powerpoint-roundtrip-report.json","p4-fidelity-inheritance.json","exception-review-hashes.json"):
            write(inputs/name,{"deck_id":"D03","name":name})
        call_dir=root/".agent-calls"/"01"/"reviewer"/"call-1"
        command=[sys.executable,str(SCRIPTS/"prepare_agent_call.py"),"--role","reviewer","--mode","deck_consistency","--work-root",str(root),"--task-id","D03","--input-root",str(inputs),"--iteration","1","--model-selection-mode","runtime-default","--call-id","call-1","--output-dir",str(call_dir),"--run-id","test"]
        completed=subprocess.run(command,capture_output=True,text=True);self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
        manifest=json.loads((call_dir/"call_manifest.json").read_text());self.assertEqual(manifest["input_profile"],"deck_consistency");self.assertEqual(manifest["selected_output_schema"],"deck-consistency-reviewer-response.schema.json")
        write(call_dir/"raw_response.json",response())
        record={"schema_version":"1.3","task_id":"D03","iteration":1,"role":"reviewer","role_version":"1.4.0","model_selection_mode":"runtime-default","requested_model":None,"config_sha256":manifest["config_sha256"],"prompt_sha256":manifest["prompt_sha256"],"output_schema_sha256":manifest["output_schema_sha256"],"input_sha256":{item["name"]:item["sha256"] for item in manifest["inputs"]},"parameters":manifest["parameters"],"call_id":"call-1","context_id":"fresh-context-1","parent_context_id":None,"status":"succeeded"};write(call_dir/"call_record.json",record)
        return call_dir,inputs

    def test_mode_specific_schema_and_fixture_finalization(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);call_dir,_=self.prepare(root);evidence=root/"evidence"
            run=subprocess.run([sys.executable,str(SCRIPTS/"finalize_agent_response.py"),"--role","reviewer","--mode","deck_consistency","--call-dir",str(call_dir),"--output-dir",str(evidence),"--run-id","test","--iteration","1","--evidence-mode","fixture"],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            result=validate_p5_reviewer_evidence(evidence,require_live=False);self.assertFalse(result["call_record"]["live"])
            with self.assertRaises(ContractError):validate_p5_reviewer_evidence(evidence,require_live=True)

    def test_live_ledger_and_tamper_detection(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);call_dir,_=self.prepare(root);evidence=root/"evidence";ledger=root/"ledger.json";write(ledger,{"calls":[{"role":"reviewer","call_id":"call-1","live":True,"status":"succeeded"}]})
            run=subprocess.run([sys.executable,str(SCRIPTS/"finalize_agent_response.py"),"--role","reviewer","--mode","deck_consistency","--call-dir",str(call_dir),"--output-dir",str(evidence),"--run-id","test","--iteration","1","--evidence-mode","live","--call-ledger",str(ledger)],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertTrue(validate_p5_reviewer_evidence(evidence,require_live=True)["call_record"]["live"])
            (evidence/"inputs"/"approved-preview-contact-sheet.png").write_bytes(b"tampered")
            with self.assertRaises(ContractError):validate_p5_reviewer_evidence(evidence,require_live=True)

    def test_legacy_profiles_remain_selectable(self)->None:
        self.assertEqual(load_role("planner",mode="initial")[3].name,"planner-response.schema.json")
        self.assertEqual(load_role("reviewer",mode="review")[3].name,"reviewer-response.schema.json")


if __name__=="__main__":unittest.main()
