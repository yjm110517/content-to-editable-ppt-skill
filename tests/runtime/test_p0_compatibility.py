from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from text_identity import build_compatibility_map, compatibility_view, compare_authority


class P0CompatibilityTests(unittest.TestCase):
    def _artifacts(self, case_id: str) -> tuple[dict, dict]:
        case_root = ROOT / "baseline" / "cases" / case_id
        report = json.loads((case_root / "case-report.json").read_text(encoding="utf-8"))
        iteration = f"{report['final_iteration']:02d}"
        layout = json.loads((case_root / "evidence" / "iterations" / iteration / "layout.json").read_text(encoding="utf-8"))
        authority = json.loads((case_root / "evidence" / "baseline-source-content.json").read_text(encoding="utf-8"))
        return layout, authority

    def test_b01_freezes_missing_footer(self) -> None:
        layout, authority = self._artifacts("B01")
        mapping = build_compatibility_map(layout, authority)
        self.assertEqual(mapping["unresolved"], [{"content_ref": "footer", "reason": "missing", "candidate_element_ids": []}])
        view = compatibility_view(layout, mapping, strict=False)
        self.assertEqual(compare_authority(authority, view)["missing"], ["footer"])

    def test_b02_through_b06_have_deterministic_identity_views(self) -> None:
        for case_id in ("B02", "B03", "B04", "B05", "B06"):
            with self.subTest(case_id=case_id):
                layout, authority = self._artifacts(case_id)
                mapping = build_compatibility_map(layout, authority)
                self.assertEqual(mapping["unresolved"], [])
                view = compatibility_view(layout, mapping)
                self.assertEqual(compare_authority(authority, view)["status"], "pass")


if __name__ == "__main__":
    unittest.main()
