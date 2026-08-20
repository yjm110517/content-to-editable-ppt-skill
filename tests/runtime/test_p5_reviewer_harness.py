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
from agent_request_evidence import request_evidence_sha256, transport_request_sha256
from asset_common import sha256_file
from p5_reviewer_evidence import validate_p5_reviewer_evidence
from schema_utils import ContractError


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def response(version: str = "1.0") -> dict:
    return {"schema_version":version,"artifact_type":"deck_consistency_reviewer_response","deck_id":"D03","reviewer_recommendation":"pass","issues":[],"mandatory_checks":{"typography_consistent":True,"palette_consistent":True,"background_consistent":True,"card_language_consistent":True,"density_spacing_consistent":True,"visual_treatment_consistent":True,"navigation_consistent":True,"section_hierarchy_consistent":True,"same_deck_identity":True,"no_reopened_p4_fidelity":True},"structured_upstream_revision":None}


class P5ReviewerHarnessTests(unittest.TestCase):
    def prepare(self, root: Path, *, live_response: bool = False) -> tuple[Path, Path]:
        inputs = root / "review-inputs"; inputs.mkdir()
        for name in ("approved-preview-contact-sheet.png","final-candidate-contact-sheet.png","approved-vs-final-comparison-sheet.png"):
            Image.new("RGB",(32,18),"white").save(inputs/name)
        for name in ("deck-visual-system-summary.json","deck-final-qa-report.json","powerpoint-roundtrip-report.json","p4-fidelity-inheritance.json","exception-review-hashes.json"):
            write(inputs/name,{"deck_id":"D03","name":name})
        call_dir=root/".agent-calls"/"01"/"reviewer"/"call-1"
        command=[sys.executable,str(SCRIPTS/"prepare_agent_call.py"),"--role","reviewer","--mode","deck_consistency","--work-root",str(root),"--task-id","D03","--input-root",str(inputs),"--iteration","1","--model-selection-mode","runtime-default","--call-id","call-1","--output-dir",str(call_dir),"--run-id","test"]
        completed=subprocess.run(command,capture_output=True,text=True);self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
        manifest=json.loads((call_dir/"call_manifest.json").read_text());self.assertEqual(manifest["input_profile"],"deck_consistency");self.assertEqual(manifest["selected_output_schema"],"deck-consistency-reviewer-response.schema.json")
        write(call_dir/"raw_response.json",response("1.1" if live_response else "1.0"))
        identity={"schema_version":"1.0","artifact_type":"reviewer_model_identity","provider":"test-provider","model_id":"test-vision","model_version_or_runtime_fingerprint":"test-runtime-v1","transport_class":"fixture-transport","endpoint_class":"test-endpoint","parameters":manifest["parameters"]}
        identity_sha=request_evidence_sha256(identity)
        request_sha=transport_request_sha256(call_manifest_sha256=sha256_file(call_dir/"call_manifest.json"),manifest=manifest,model_identity_sha256=identity_sha)
        record={"schema_version":"1.3","task_id":"D03","iteration":1,"role":"reviewer","role_version":"1.4.0","model_selection_mode":"runtime-default","requested_model":None,"config_sha256":manifest["config_sha256"],"prompt_sha256":manifest["prompt_sha256"],"output_schema_sha256":manifest["output_schema_sha256"],"input_sha256":{item["name"]:item["sha256"] for item in manifest["inputs"]},"parameters":manifest["parameters"],"call_id":"call-1","context_id":"fresh-context-1","parent_context_id":None,"status":"succeeded","resolved_model_identity":identity,"resolved_model_identity_sha256":identity_sha,"transport_request_sha256":request_sha,"prepared_at_utc":"2026-08-20T00:00:00Z","invoked_at_utc":"2026-08-20T00:00:01Z","completed_at_utc":"2026-08-20T00:00:02Z"};write(call_dir/"call_record.json",record)
        return call_dir,inputs

    def test_mode_specific_schema_and_fixture_finalization(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);call_dir,_=self.prepare(root);evidence=root/"evidence"
            run=subprocess.run([sys.executable,str(SCRIPTS/"finalize_agent_response.py"),"--role","reviewer","--mode","deck_consistency","--call-dir",str(call_dir),"--output-dir",str(evidence),"--run-id","test","--iteration","1","--evidence-mode","fixture"],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            result=validate_p5_reviewer_evidence(evidence,require_live=False);self.assertFalse(result["call_record"]["live"])
            with self.assertRaises(ContractError):validate_p5_reviewer_evidence(evidence,require_live=True)

    def test_live_ledger_and_tamper_detection(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);call_dir,_=self.prepare(root,live_response=True);evidence=root/"evidence";ledger=root/"ledger.json";write(ledger,{"calls":[{"role":"reviewer","call_id":"call-1","live":True,"status":"succeeded"}]})
            run=subprocess.run([sys.executable,str(SCRIPTS/"finalize_agent_response.py"),"--role","reviewer","--mode","deck_consistency","--call-dir",str(call_dir),"--output-dir",str(evidence),"--run-id","test","--iteration","1","--evidence-mode","live","--call-ledger",str(ledger)],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertTrue(validate_p5_reviewer_evidence(evidence,require_live=True)["call_record"]["live"])
            (evidence/"inputs"/"approved-preview-contact-sheet.png").write_bytes(b"tampered")
            with self.assertRaises(ContractError):validate_p5_reviewer_evidence(evidence,require_live=True)

    def test_input_metadata_and_transport_identity_tampering_rejected(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);call_dir,_=self.prepare(root,live_response=True)
            manifest=json.loads((call_dir/"call_manifest.json").read_text())
            self.assertEqual(manifest["inputs"][0]["media_type"],"image/png")
            self.assertEqual(manifest["inputs"][0]["purpose"],"approved_preview_contact_sheet")
            manifest["inputs"][0]["purpose"]="wrong"
            write(call_dir/"call_manifest.json",manifest)
            with self.assertRaises(Exception):
                from agent_common import load_call_bundle
                load_call_bundle(call_dir,work_root=root,role="reviewer",mode="deck_consistency")

    def test_live_v10_and_model_identity_tampering_rejected(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);call_dir,_=self.prepare(root);ledger=root/"ledger.json";write(ledger,{"calls":[{"role":"reviewer","call_id":"call-1","live":True,"status":"succeeded"}]})
            rejected=subprocess.run([sys.executable,str(SCRIPTS/"finalize_agent_response.py"),"--role","reviewer","--mode","deck_consistency","--call-dir",str(call_dir),"--output-dir",str(root/"v10-evidence"),"--run-id","test","--iteration","1","--evidence-mode","live","--call-ledger",str(ledger)],capture_output=True,text=True)
            self.assertNotEqual(rejected.returncode,0)

        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);call_dir,_=self.prepare(root,live_response=True)
            record=json.loads((call_dir/"call_record.json").read_text());record["resolved_model_identity"]["model_id"]="tampered-model";write(call_dir/"call_record.json",record)
            from agent_common import load_call_bundle
            with self.assertRaises(Exception):load_call_bundle(call_dir,work_root=root,role="reviewer",mode="deck_consistency")

    def test_legacy_profiles_remain_selectable(self)->None:
        self.assertEqual(load_role("planner",mode="initial")[3].name,"planner-response.schema.json")
        self.assertEqual(load_role("reviewer",mode="review")[3].name,"reviewer-response.schema.json")


if __name__=="__main__":unittest.main()
