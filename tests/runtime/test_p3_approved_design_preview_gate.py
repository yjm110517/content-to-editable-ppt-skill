from __future__ import annotations
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];REPORT=ROOT/"reports"/"p3"/"p3-approved-design-preview-gate.json"
class ApprovedDesignPreviewGateTests(unittest.TestCase):
    def test_committed_gate_separates_manual_and_automated_evidence(self):
        report=json.loads(REPORT.read_text(encoding="utf-8"));self.assertEqual(report["status"],"pass");self.assertEqual(report["manual_acceptance_evidence"],"pass");self.assertEqual(report["automated_regression_replay"],"pass");self.assertEqual(set(report["review_run"].values()),{0});self.assertEqual(report["d03"]["image_generation_calls"],3);self.assertEqual(report["generated_layer_direct_approval"],0);self.assertTrue(report["p0_baseline_unchanged"])
if __name__=="__main__":unittest.main()
