from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location("p5_eval",ROOT/"tools"/"delivery"/"p5_delivery_eval.py");P5=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(P5)


class P5LiveConsumerTests(unittest.TestCase):
    def test_clean_live_review_runs_policy_decision_package_and_verify(self)->None:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);gate=root/"D03";inputs=gate/"review-inputs";inputs.mkdir(parents=True)
            mapping={"approved-preview-contact-sheet.png":gate/"approved-preview-contact-sheet.png","final-candidate-contact-sheet.png":gate/"final-candidate-contact-sheet.png","approved-vs-final-comparison-sheet.png":gate/"approved-vs-final-comparison-sheet.png","deck-visual-system-summary.json":inputs/"deck-visual-system-summary.json","deck-final-qa-report.json":inputs/"deck-final-qa-report.json","powerpoint-roundtrip-report.json":inputs/"powerpoint-roundtrip-report.json","p4-fidelity-inheritance.json":inputs/"p4-fidelity-inheritance.json","exception-review-hashes.json":inputs/"exception-review-hashes.json"}
            for path in mapping.values():path.write_bytes(path.name.encode())
            for name in ("deck-evidence.json","qa-report.json","roundtrip-report.json","final-render-manifest.json","runtime-lock.json","state.json"):(gate/name).write_text(json.dumps({"state":"delivery_approved"}) if name=="state.json" else "{}")
            p4=root/"p4";p4.mkdir();(p4/"reconstruction-candidate.pptx").write_bytes(b"pptx");(p4/"candidate-deck-report.json").write_text("{}");(p4/"reconstruction-asset-manifest.json").write_text("{}")
            trusted={"manifest":{"task_id":"D03"},"call_record":{"context_id":"ctx","resolved_model_identity_sha256":"c"*64,"transport_request_sha256":"d"*64,"technical_retry_count":0},"response":{"reviewer_recommendation":"pass"},"input_hashes":{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in mapping.items()}}
            calls=[]
            def fake_cli(*args):
                calls.append(args);command=args[0]
                if command=="evaluate":return {"policy_status":"pass"}
                if command=="package":return {"dist":str(root/"dist"),"delivered_pptx_sha256":"a"*64,"provenance_sha256":"b"*64,"files":{f"file-{index}":"0"*64 for index in range(7)}}
                if command=="verify":return {"delivery_artifact_hash_closure":"pass"}
                return {}
            with patch.object(P5,"_validate_live_evidence",return_value=trusted),patch.object(P5,"_cli",side_effect=fake_cli):
                result=P5.run_consume_live(root/"evidence",root,p4_evidence_root=p4,dist_root=root/"dist-root",output_name="deck",report_path=root/"final.json")
            self.assertEqual(result["status"],"pass");self.assertTrue(result["formal_delivery_created"])
            self.assertEqual(result["formal_delivery_file_count"],7);self.assertEqual(result["delivery_artifact_hash_closure"],"pass")
            self.assertEqual([item[0] for item in calls],["record-deck-review","evaluate","create-decision","package","verify"])

if __name__=="__main__":unittest.main()
