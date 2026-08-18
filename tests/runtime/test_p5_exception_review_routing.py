from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys_path = str(ROOT / "content-to-editable-ppt" / "scripts")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from exception_review_evidence import build_exception_batches  # noqa: E402
from schema_utils import ContractError  # noqa: E402

BUDGET = {"batch_size": 4, "batch_calls": 2}


def _issue(seed: str, slide_ids: list[str]) -> dict:
    import hashlib
    return {"issue_id": "P5-" + hashlib.sha256(seed.encode()).hexdigest()[:12].upper(), "severity": "major", "slide_ids": slide_ids, "code": "deck_qa_code", "message": seed}


class P5ExceptionReviewRoutingTests(unittest.TestCase):
    def test_no_exception_pages_yields_empty_batches(self) -> None:
        evidence = build_exception_batches(deck_id="D03", exception_pages=[], issues=[], budget=BUDGET)
        self.assertEqual(evidence["batches"], [])
        self.assertEqual(evidence["bound_issue_ids"], [])

    def test_batching_respects_size_and_binding(self) -> None:
        issues = [{"issue_id": f"P5-I{index:04d}", "severity": "major", "slide_ids": [f"S{index:02d}"], "code": "c", "message": "m"} for index in range(1, 7)]
        evidence = build_exception_batches(deck_id="D03", exception_pages=[f"S{index:02d}" for index in range(1, 7)], issues=issues, budget=BUDGET)
        self.assertEqual(len(evidence["batches"]), 2)
        self.assertEqual(len(evidence["batches"][0]["slide_ids"]), 4)
        self.assertEqual(len(evidence["batches"][1]["slide_ids"]), 2)
        for batch in evidence["batches"]:
            self.assertTrue(batch["bound_issue_ids"])

    def test_unbound_exception_page_rejected(self) -> None:
        issues = [{"issue_id": "P5-ABC123DEF456", "severity": "major", "slide_ids": ["S01"], "code": "c", "message": "m"}]
        with self.assertRaises(ContractError):
            build_exception_batches(deck_id="D03", exception_pages=["S01", "S02"], issues=issues, budget=BUDGET)

    def test_systemic_failure_over_eight_pages(self) -> None:
        pages = [f"S{index:02d}" for index in range(1, 10)]
        with self.assertRaises(ContractError) as context:
            build_exception_batches(deck_id="D03", exception_pages=pages, issues=[], budget=BUDGET)
        self.assertEqual(context.exception.errors[0]["code"], "systemic_visual_failure")

    def test_budget_mismatch_rejected(self) -> None:
        with self.assertRaises(ContractError):
            build_exception_batches(deck_id="D03", exception_pages=[], issues=[], budget={"batch_size": 5, "batch_calls": 3})


if __name__ == "__main__":
    unittest.main()