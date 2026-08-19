from __future__ import annotations

from pathlib import Path
from typing import Any

from schema_utils import ContractError, error, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


def build_exception_batches(*, deck_id: str, exception_pages: list[str], issues: list[dict[str, Any]], budget: dict[str, int]) -> dict[str, Any]:
    """Group exception pages into issue-bound review batches.

    - batch_size <= 4, batch_calls <= 2 (frozen budgets; accepts both state-style
      exception_batch_size/exception_batch_calls and plain batch_size/batch_calls keys);
    - more than 8 exception pages -> systemic_visual_failure (return to P4);
    - every batch binds the QA issue ids of its slides.
    """
    batch_size = budget.get("exception_batch_size", budget.get("batch_size"))
    batch_calls = budget.get("exception_batch_calls", budget.get("batch_calls"))
    if batch_size != 4 or batch_calls != 2:
        raise ContractError([error("$.budget", "exception review budgets are frozen at batch_size=4, batch_calls=2", "budget_mismatch")])
    budget = {"batch_size": batch_size, "batch_calls": batch_calls}
    if len(exception_pages) > 8:
        raise ContractError([error("$.exception_pages", "more than 8 exception pages is a systemic visual failure", "systemic_visual_failure")])
    pages = sorted(exception_pages)
    issue_by_page: dict[str, list[str]] = {}
    for issue in issues:
        for slide_id in issue.get("slide_ids", []):
            issue_by_page.setdefault(slide_id, []).append(issue["issue_id"])
    batches: list[dict[str, Any]] = []
    for index in range(0, len(pages), budget["batch_size"]):
        batch_pages = pages[index:index + budget["batch_size"]]
        bound: list[str] = []
        for page in batch_pages:
            if not issue_by_page.get(page):
                raise ContractError([error(f"$.exception_pages[{index}]", f"exception page {page} must bind at least one QA issue", "unbound_exception_page")])
            bound.extend(issue_by_page[page])
        bound = sorted(set(bound))
        batches.append({"batch_index": len(batches) + 1, "slide_ids": batch_pages, "bound_issue_ids": bound})
    document = {
        "schema_version": "1.0",
        "artifact_type": "exception_review_evidence",
        "deck_id": deck_id,
        "batch_slide_ids": pages,
        "bound_issue_ids": sorted({item for batch in batches for item in batch["bound_issue_ids"]}),
        "budget": {"batch_size": budget["batch_size"], "batch_calls": budget["batch_calls"]},
        "batches": batches,
        "ledger_entry": None,
    }
    return document
