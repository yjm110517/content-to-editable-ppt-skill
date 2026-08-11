from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


class AgentBudgetError(RuntimeError):
    pass


class AgentAdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class AgentCallLedger:
    allow_live: bool = False
    budget: int = 0
    calls: list[dict[str, Any]] = field(default_factory=list)

    def reserve(self, *, role: str, call_id: str, live: bool) -> None:
        if live and not self.allow_live:
            raise AgentBudgetError("live Agent calls require explicit authorization")
        if live and len([item for item in self.calls if item["live"]]) >= self.budget:
            raise AgentBudgetError("Agent call budget exhausted")
        self.calls.append({"role": role, "call_id": call_id, "live": live, "status": "reserved"})

    @property
    def live_call_count(self) -> int:
        return len([item for item in self.calls if item["live"]])

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"live_call_count": self.live_call_count, "calls": self.calls}, indent=2), encoding="utf-8")


class FixtureAdapter:
    mode = "fixture"

    def __init__(self, response: dict[str, Any]):
        self.response = response

    def invoke(self, *, role: str, call_id: str, ledger: AgentCallLedger) -> dict[str, Any]:
        ledger.reserve(role=role, call_id=call_id, live=False)
        return copy.deepcopy(self.response)


class FailureAdapter:
    mode = "failure"

    def __init__(self, code: str):
        self.code = code

    def invoke(self, *, role: str, call_id: str, ledger: AgentCallLedger) -> dict[str, Any]:
        ledger.reserve(role=role, call_id=call_id, live=False)
        raise AgentAdapterError(self.code, f"injected {self.code}")


class TimeoutTestAdapter:
    mode = "timeout_test"

    def __init__(self, sleep_seconds: float = 6.0):
        self.sleep_seconds = sleep_seconds

    def invoke(self, *, role: str, call_id: str, ledger: AgentCallLedger) -> dict[str, Any]:
        ledger.reserve(role=role, call_id=call_id, live=False)
        time.sleep(self.sleep_seconds)
        return {"status": "unexpected_completion"}


class LiveAdapter:
    mode = "live"

    def __init__(self, transport: Callable[[], dict[str, Any]]):
        self.transport = transport

    def invoke(self, *, role: str, call_id: str, ledger: AgentCallLedger) -> dict[str, Any]:
        ledger.reserve(role=role, call_id=call_id, live=True)
        return self.transport()
