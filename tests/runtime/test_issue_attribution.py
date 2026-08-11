from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from issue_attribution import EVIDENCE_KEYS, attribute_issue
from schema_utils import validate_schema


SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"


class IssueAttributionTests(unittest.TestCase):
    def evidence(self, **updates: bool) -> dict[str, bool]:
        result = {key: False for key in EVIDENCE_KEYS}
        result.update(updates)
        return result

    def test_deterministic_regression_is_blocking(self) -> None:
        report = attribute_issue(case_id="B04", reviewer_severity="major", deterministic_evidence=self.evidence(topology_regression=True), pre_existing_visual_issue=False)
        self.assertEqual(report["classification"], "runtime_regression")
        validate_schema("issue_attribution", report, SCHEMA_DIR)

    def test_reviewer_only_change_is_variance_candidate(self) -> None:
        report = attribute_issue(case_id="B03", reviewer_severity="major", deterministic_evidence=self.evidence(), pre_existing_visual_issue=False)
        self.assertEqual(report["classification"], "agent_variance_candidate")

    def test_matching_frozen_issue_is_pre_existing(self) -> None:
        report = attribute_issue(case_id="B01", reviewer_severity="major", deterministic_evidence=self.evidence(), pre_existing_visual_issue=True)
        self.assertEqual(report["classification"], "pre_existing_visual_issue")


if __name__ == "__main__":
    unittest.main()
