from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from schema_utils import ContractError
from shared_validator import validate_documents


SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"


class SharedValidatorTests(unittest.TestCase):
    def _documents(self, case_id: str = "B03") -> dict:
        case = ROOT / "baseline" / "cases" / case_id
        report = json.loads((case / "case-report.json").read_text(encoding="utf-8"))
        iteration = case / "evidence" / "iterations" / f"{report['final_iteration']:02d}"
        return {
            "request": json.loads((case / "input" / "request.json").read_text(encoding="utf-8")),
            "layout": json.loads((iteration / "layout.json").read_text(encoding="utf-8")),
            "crops": json.loads((iteration / "crops.json").read_text(encoding="utf-8")),
            "asset_manifest": json.loads((iteration / "asset_manifest.json").read_text(encoding="utf-8")),
        }

    def test_candidate_does_not_require_processed_files(self) -> None:
        documents = self._documents()
        validate_documents(documents, {}, profile="candidate", schema_dir=SCHEMA_DIR)

    def test_unsupported_background_removal_fails_before_build(self) -> None:
        documents = self._documents()
        documents["crops"]["assets"][0]["remove_background"] = True
        with self.assertRaises(ContractError) as raised:
            validate_documents(documents, {}, profile="candidate", schema_dir=SCHEMA_DIR)
        self.assertIn("unsupported_operation", {item["code"] for item in raised.exception.errors})

    def test_crop_box_semantics_are_left_top_right_bottom(self) -> None:
        documents = self._documents()
        documents["crops"]["assets"][0]["box_px"] = [200, 100, 100, 200]
        with self.assertRaises(ContractError) as raised:
            validate_documents(documents, {}, profile="candidate", schema_dir=SCHEMA_DIR)
        self.assertIn("invalid_crop_box", {item["code"] for item in raised.exception.errors})

    def test_layout_14_requires_content_identity(self) -> None:
        documents = self._documents("B06")
        documents["layout"]["schema_version"] = "1.4"
        with self.assertRaises(ContractError) as raised:
            validate_documents(documents, {}, profile="candidate", schema_dir=SCHEMA_DIR)
        self.assertIn("content_identity", {item["code"] for item in raised.exception.errors})


if __name__ == "__main__":
    unittest.main()
