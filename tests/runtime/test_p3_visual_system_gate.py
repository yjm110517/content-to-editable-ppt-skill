from __future__ import annotations
import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];REPORT=ROOT/"reports"/"p3"/"p3-visual-system-prompt-contract-gate.json"
class VisualSystemGateTests(unittest.TestCase):
    def test_committed_gate_is_contract_only(self)->None:
        report=json.loads(REPORT.read_text(encoding="utf-8"));self.assertEqual(report["contract_prompt_gate"],"pass");self.assertEqual(report["visual_quality_status"],"not_evaluated");self.assertEqual(report["recorded_d03_host_model_invocations"],1);self.assertEqual(set(report["review_run"].values()),{0});self.assertTrue(all(item["status"]=="pass" for item in report["cases"]));self.assertTrue(report["p0_baseline_unchanged"])
if __name__=="__main__":unittest.main()
