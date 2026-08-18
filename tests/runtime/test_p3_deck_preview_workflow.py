from __future__ import annotations
import argparse,tempfile,unittest,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"content-to-editable-ppt"/"scripts"));FIX=ROOT/"tests"/"fixtures"/"p3"/"d03-style-anchor"
from deck_preview_workflow import contact_sheet,prepare_page
class DeckPreviewWorkflowTests(unittest.TestCase):
    def test_page_package_and_contact_sheet_are_deterministic_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);prepare_page(argparse.Namespace(prompt_package=FIX/"deck-prompt-package.json",style_reference_record=FIX/"style-anchor-reference-record.json",runtime_lock=FIX/"generation-runtime-lock.json",slide_id="S01",output_dir=root/"call"));self.assertTrue((root/"call"/"prompt.txt").is_file())
            result=contact_sheet(argparse.Namespace(style_anchor_record=FIX/"style-anchor-record.json",preview_record=[FIX/"final-design-preview-record.json"],preview_image=[FIX/"final-design-preview.png"],output_manifest=root/"manifest.json",output_image=root/"sheet.png",output_record=root/"sheet.json"));self.assertTrue((root/"sheet.png").is_file());self.assertEqual(json.loads((root/"manifest.json").read_text())["status"],"ready_for_confirmation")
if __name__=="__main__":unittest.main()
