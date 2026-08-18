from __future__ import annotations
import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];FIXTURE=ROOT/"tests"/"fixtures"/"p3"/"d03-style-anchor"
class ManualAnchorEvidenceTests(unittest.TestCase):
    def test_manual_acceptance_evidence_is_closed(self):
        preview=json.loads((FIXTURE/"final-design-preview-record.json").read_text(encoding="utf-8"));feedback=json.loads((FIXTURE/"style-anchor-feedback.json").read_text(encoding="utf-8"));anchor=json.loads((FIXTURE/"style-anchor-record.json").read_text(encoding="utf-8"));compat=json.loads((FIXTURE/"reconstruction-compatibility-report.json").read_text(encoding="utf-8"));call=json.loads((FIXTURE/"call_record.json").read_text(encoding="utf-8"))
        self.assertEqual(preview["final_preview_sha256"],hashlib.sha256((FIXTURE/"final-design-preview.png").read_bytes()).hexdigest());self.assertFalse(preview["generated_layer_direct_approval"]);self.assertEqual(feedback["decision"],"accepted");self.assertEqual(feedback["final_preview_sha256"],preview["final_preview_sha256"]);self.assertEqual(anchor["status"],"approved");self.assertEqual(compat["status"],"pass");self.assertEqual(call["technical_retry_count"],0);self.assertEqual(call["generation_kind"],"initial")
if __name__=="__main__":unittest.main()
