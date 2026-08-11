from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from agent_adapters import AgentBudgetError, AgentCallLedger, FailureAdapter, FixtureAdapter, LiveAdapter


class AgentAdapterTests(unittest.TestCase):
    def test_fixture_never_consumes_live_budget(self) -> None:
        ledger = AgentCallLedger()
        result = FixtureAdapter({"status": "ok"}).invoke(role="planner", call_id="fixture-1", ledger=ledger)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(ledger.live_call_count, 0)

    def test_live_requires_explicit_authorization(self) -> None:
        ledger = AgentCallLedger(allow_live=False, budget=1)
        with self.assertRaises(AgentBudgetError):
            LiveAdapter(lambda: {"status": "ok"}).invoke(role="planner", call_id="live-1", ledger=ledger)

    def test_live_budget_is_hard_limit(self) -> None:
        ledger = AgentCallLedger(allow_live=True, budget=1)
        adapter = LiveAdapter(lambda: {"status": "ok"})
        adapter.invoke(role="planner", call_id="live-1", ledger=ledger)
        with self.assertRaises(AgentBudgetError):
            adapter.invoke(role="planner", call_id="live-2", ledger=ledger)

    def test_failure_is_deterministic_and_not_live(self) -> None:
        ledger = AgentCallLedger()
        with self.assertRaisesRegex(RuntimeError, "reviewer_timeout"):
            FailureAdapter("reviewer_timeout").invoke(role="reviewer", call_id="failure-1", ledger=ledger)
        self.assertEqual(ledger.live_call_count, 0)


if __name__ == "__main__":
    unittest.main()
