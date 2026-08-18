from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

class P4GateTests(unittest.TestCase):
    def test_frozen_gate_closes_reconstruction_and_assembly(self)->None:
        report=json.loads((ROOT/"reports"/"p4"/"p4-constrained-reconstruction-gate.json").read_text(encoding="utf-8"));self.assertEqual(report["status"],"pass");self.assertEqual(report["blocking_issues"],0);self.assertEqual(report["seed_completeness_percent"],100);self.assertEqual(report["native_required_editability_percent"],100);self.assertEqual(report["post_assembly_slide_drift"],0);self.assertEqual(report["unexpected_assembly_mutation"],0);self.assertTrue(report["delivery_forbidden"])
        cases={item["case_id"]:item for item in report["cases"]};self.assertEqual(set(cases),{"D03","D05","D08"});self.assertEqual(cases["D03"]["slides"],3);self.assertTrue(all(item["classification"]=="pass" for item in cases["D03"]["reconstruction_fidelity"]));self.assertEqual(report["review_run"]["host_calls"],0);self.assertEqual(report["review_run"]["image_generation_calls"],0)

if __name__=="__main__":unittest.main()
