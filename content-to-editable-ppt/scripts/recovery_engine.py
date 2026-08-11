from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

from asset_common import atomic_write_json, sha256_file
from iteration_common import utc_now


MAX_TECHNICAL_RETRIES = 2
MAX_FULL_REPLANS = 1
MAX_TOTAL_ITERATIONS = 3


class RecoveryError(RuntimeError):
    pass


def migrate_run_state_v14(state: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(state)
    if result.get("schema_version") == "1.4":
        return result
    if result.get("schema_version") != "1.3":
        raise RecoveryError("only run_state 1.3 can be migrated to 1.4")
    result["schema_version"] = "1.4"
    result.setdefault("current_stage", None)
    result.setdefault("counters", {"planner_calls": 0, "reviewer_calls": 0, "full_semantic_replans": 0, "targeted_revisions": max(0, result.get("current_iteration", 1) - 1), "technical_retries": 0, "runtime_repairs": 0})
    result.setdefault("stages", {})
    result.setdefault("last_failure", None)
    result.setdefault("reclassifications", [])
    return result


def hash_inputs(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted((item.resolve() for item in paths), key=lambda item: str(item).lower()):
        digest.update(path.name.encode("utf-8"))
        if path.is_dir():
            for child in sorted((item for item in path.rglob("*") if item.is_file()), key=lambda item: item.relative_to(path).as_posix()):
                digest.update(child.relative_to(path).as_posix().encode("utf-8"))
                digest.update(bytes.fromhex(sha256_file(child)))
        else:
            digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def _output_records(paths: list[Path], root: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for path in paths:
        if not path.is_file():
            raise RecoveryError(f"stage output is missing: {path.name}")
        records.append({"path": path.resolve().relative_to(root.resolve()).as_posix(), "sha256": sha256_file(path)})
    return records


class StageLedger:
    def __init__(self, path: Path, *, root: Path, production_state: bool = False):
        self.path = path.resolve()
        self.root = root.resolve()
        self.production_state = production_state
        if self.path.is_file():
            document = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = migrate_run_state_v14(document) if production_state else document
        elif production_state:
            raise RecoveryError("production run_state does not exist")
        else:
            self.state = {"schema_version": "1.0", "current_stage": None, "counters": {"technical_retries": 0, "full_semantic_replans": 0, "targeted_revisions": 0}, "stages": {}, "last_failure": None, "reclassifications": []}

    def save(self) -> None:
        atomic_write_json(self.path, self.state)

    def reusable(self, name: str, input_sha256: str) -> bool:
        record = self.state["stages"].get(name)
        if not record or record["status"] not in {"passed", "reused"} or record["input_sha256"] != input_sha256:
            return False
        for output in record["outputs"]:
            path = self.root / output["path"]
            if not path.is_file() or sha256_file(path) != output["sha256"]:
                return False
        return True

    def skip(self, name: str, input_sha256: str) -> None:
        self.state["current_stage"] = name
        self.state["stages"][name] = {"status": "skipped", "input_sha256": input_sha256, "outputs": [], "attempt_count": 0, "completed_at_utc": utc_now()}
        self.save()

    def run(
        self,
        name: str,
        *,
        inputs: list[Path],
        outputs: list[Path],
        action: Callable[[], None],
        resume: bool = False,
        retryable: Callable[[Exception], bool] | None = None,
    ) -> str:
        input_sha = hash_inputs(inputs)
        if resume and self.reusable(name, input_sha):
            self.state["current_stage"] = name
            self.state["stages"][name]["status"] = "reused"
            self.save()
            return "reused"
        for attempt in range(MAX_TECHNICAL_RETRIES + 1):
            self.state["current_stage"] = name
            self.state["stages"][name] = {"status": "running", "input_sha256": input_sha, "outputs": [], "attempt_count": attempt + 1, "completed_at_utc": None}
            self.save()
            try:
                action()
                self.state["stages"][name] = {"status": "passed", "input_sha256": input_sha, "outputs": _output_records(outputs, self.root), "attempt_count": attempt + 1, "completed_at_utc": utc_now()}
                self.state["last_failure"] = None
                self.save()
                return "passed"
            except Exception as exc:
                can_retry = retryable(exc) if retryable else False
                if not can_retry or attempt >= MAX_TECHNICAL_RETRIES:
                    self.state["stages"][name] = {"status": "failed", "input_sha256": input_sha, "outputs": [], "attempt_count": attempt + 1, "completed_at_utc": utc_now()}
                    self.state["last_failure"] = {"schema_version": "1.0", "code": getattr(exc, "code", "technical_failure"), "category": "technical_failure", "stage": name, "recoverable": can_retry, "issue_scope": "stage", "artifact_path": None, "normalized_message": str(exc), "attempt": attempt}
                    self.save()
                    raise
                self.state["counters"]["technical_retries"] += 1
                self.save()
        raise AssertionError("unreachable")


def authorize_global_replan(state: dict[str, Any], evidence: list[str]) -> dict[str, Any]:
    if not evidence or any(not item.strip() for item in evidence):
        raise RecoveryError("global semantic reclassification requires evidence")
    updated = migrate_run_state_v14(state)
    counters = updated["counters"]
    if counters["full_semantic_replans"] >= MAX_FULL_REPLANS:
        raise RecoveryError("full semantic replan limit reached")
    if 1 + counters["targeted_revisions"] + counters["full_semantic_replans"] >= MAX_TOTAL_ITERATIONS:
        raise RecoveryError("total iteration limit reached")
    counters["full_semantic_replans"] += 1
    updated["reclassifications"].append({"from": "local_spec_failure", "to": "global_semantic_failure", "evidence": evidence, "timestamp_utc": utc_now()})
    return updated


def authorize_targeted_revision(state: dict[str, Any]) -> dict[str, Any]:
    updated = migrate_run_state_v14(state)
    counters = updated["counters"]
    if counters["targeted_revisions"] >= 2:
        raise RecoveryError("targeted revision limit reached")
    if 1 + counters["targeted_revisions"] + counters["full_semantic_replans"] >= MAX_TOTAL_ITERATIONS:
        raise RecoveryError("total iteration limit reached")
    counters["targeted_revisions"] += 1
    return updated


def recovery_route(category: str) -> str:
    routes = {
        "environment_failure": "runtime_repair",
        "technical_failure": "technical_retry",
        "local_spec_failure": "targeted_patch",
        "global_semantic_failure": "limited_full_replan",
        "content_failure": "fail",
        "visual_failure": "targeted_patch",
        "unrecoverable_failure": "fail",
    }
    if category not in routes:
        raise RecoveryError(f"unclassified failure category: {category}")
    return routes[category]
