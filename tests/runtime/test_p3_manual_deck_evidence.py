from __future__ import annotations
import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];FIX=ROOT/"tests"/"fixtures"/"p3";DECK=FIX/"d03-approved-deck";ANCHOR=FIX/"d03-style-anchor"
class ManualDeckEvidenceTests(unittest.TestCase):
    def test_approved_deck_evidence_closes_three_page_workflow(self):
        manifest=json.loads((DECK/"approved-design-preview-manifest.json").read_text(encoding="utf-8"));feedback=json.loads((DECK/"design-preview-feedback.json").read_text(encoding="utf-8"));self.assertEqual(manifest["status"],"approved");self.assertEqual([item["slide_id"] for item in manifest["previews"]],["S01","S02","S03"]);self.assertEqual(feedback["decision"],"accepted");self.assertEqual(feedback["affected_slide_ids"],[]);self.assertEqual(hashlib.sha256((DECK/"contact-sheet.png").read_bytes()).hexdigest(),json.loads((DECK/"contact-sheet-record.json").read_text())["contact_sheet_sha256"])
        for sid in ("S01","S02"):
            record=json.loads((DECK/sid/"final-design-preview-record.json").read_text());self.assertEqual(record["final_preview_sha256"],hashlib.sha256((DECK/sid/"final-design-preview.png").read_bytes()).hexdigest());self.assertEqual(json.loads((DECK/sid/"reconstruction-compatibility-report.json").read_text())["status"],"pass");self.assertEqual(json.loads((DECK/sid/"call_record.json").read_text())["technical_retry_count"],0)
        self.assertEqual(json.loads((ANCHOR/"reconstruction-compatibility-report.json").read_text())["status"],"pass")
if __name__=="__main__":unittest.main()
