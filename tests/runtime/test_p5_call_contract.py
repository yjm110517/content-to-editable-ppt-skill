from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.runtime.p5_test_support import (SCRIPTS, sys, create_work, fake_qa, write_review, make_patch,
                                         apply_args, atomic_write_json, load_json)
from apply_revision_patch import apply_revision


class P5CallContractTests(unittest.TestCase):
    def test_shared_identity_keeps_reviewer_response_without_mode_compatible(self):
        from finalize_agent_response import _validate_identity
        _validate_identity({"task_id": "fixture", "iteration": 1},
                           {"task_id": "fixture", "iteration": 1, "role": "reviewer", "mode": "review"}, 1)

    def work(self, root):
        work = create_work(root)
        fake_qa(work)
        write_review(work)
        return work

    def prepare(self, work, *, contract="canonical", iteration=1):
        current = work / f"iterations/{iteration:02d}"
        call = work / f".agent-calls/{iteration:02d}/planner/test-call"
        completed = subprocess.run([
            sys.executable, str(SCRIPTS / "prepare_agent_call.py"), "--role", "planner", "--mode", "revision",
            "--revision-contract", contract, "--work-root", str(work), "--request", str(work / "request.json"),
            "--source", str(work / "source.png"), "--reconstruction-handoff", str(work / "reconstruction-handoff.json"),
            "--content-authority", str(work / "source-content.json"), "--iteration-dir", str(current), "--slide-id", "S01",
            "--iteration", str(iteration), "--call-id", "test-call", "--output-dir", str(call)], capture_output=True, text=True)
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        return call, load_json(call / "call_manifest.json")

    def respond(self, call, manifest, response):
        if manifest.get("call_record_schema_version") == "1.4":
            from asset_common import sha256_file
            atomic_write_json(call / "raw_response.json", response)
            atomic_write_json(call / "call_record.json", {
                "schema_version": "1.4", "task_id": manifest["task_id"], "iteration": manifest["iteration"],
                "role": manifest["role"], "role_version": manifest["role_version"],
                "model_selection_mode": manifest["model_selection_mode"], "requested_model": manifest["requested_model"],
                "config_sha256": manifest["config_sha256"], "prompt_sha256": manifest["prompt_sha256"],
                "output_schema_sha256": manifest["output_schema_sha256"],
                "input_sha256": {item["name"]: item["sha256"] for item in manifest["inputs"]},
                "configured_parameters": manifest["parameters"],
                "parameter_observations": {name: {"status": "unavailable", "reason": "host_not_exposed"}
                                           for name in ("temperature", "top_p", "seed")},
                "call_id": manifest["call_id"], "context_id": "fixture-fresh-context",
                "parent_context_id": None, "status": "succeeded",
                "context_evidence": {"status": "observed", "method": "history_free_context",
                                     "context_id": "fixture-fresh-context", "parent_context_id": None},
                "delivered_inputs": [
                    {"name": item["name"], "sha256": item["sha256"], "media_type": item["media_type"],
                     "modality": "image" if item["name"] == "source.png" else "document"}
                    for item in manifest["inputs"]
                ],
                "raw_response_sha256": sha256_file(call / "raw_response.json"),
            })
            return
        from tests.runtime.test_p3_planner_integration import P3PlannerIntegrationTests
        P3PlannerIntegrationTests()._record_response(call, manifest, response)
        record = load_json(call / "call_record.json")
        record["iteration"] = manifest["iteration"]
        atomic_write_json(call / "call_record.json", record)

    def response(self, work, iteration=1):
        return {"schema_version": "1.5", "task_id": "p5-live-01", "iteration": iteration, "mode": "revision",
                "outcome": "patch", "artifacts": {"revision_patch": make_patch(work, iteration, value=0.40 if iteration == 1 else 0.36)}}

    def finalize(self, work, call, *, contract="canonical", iteration=1):
        return subprocess.run([sys.executable, str(SCRIPTS / "finalize_agent_response.py"), "--role", "planner", "--mode", "revision",
                               "--revision-contract", contract, "--call-dir", str(call), "--iteration-dir", str(work / f"iterations/{iteration:02d}"),
                               "--run-id", "fixture", "--iteration", str(iteration)], capture_output=True, text=True)

    def test_prepare_finalizer_apply_and_validate_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = self.work(Path(tmp))
            args = apply_args(work)
            call, manifest = self.prepare(work)
            self.assertEqual("canonical", manifest["revision_contract"])
            self.assertEqual("revision_canonical", manifest["input_profile"])
            self.assertEqual("1.4", manifest["call_record_schema_version"])
            self.assertEqual("observed-or-unavailable", manifest["sampling_evidence_policy"])
            self.assertEqual("strict-live", manifest["host_evidence_policy"])
            self.assertEqual(10, len(manifest["inputs"]))
            self.respond(call, manifest, self.response(work))
            before = (call / "raw_response.json").read_bytes()
            completed = self.finalize(work, call)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertTrue(args.patch.is_file())
            self.assertFalse(args.next_dir.exists())
            validated = subprocess.run([sys.executable, str(SCRIPTS / "validate_revision_patch.py"), "--work-root", str(work),
                                        "--current-dir", str(args.current_dir), "--patch", str(args.patch)], capture_output=True, text=True)
            self.assertEqual(0, validated.returncode, validated.stdout + validated.stderr)
            self.assertFalse(args.next_dir.exists())
            apply_revision(args)
            self.assertEqual(before, (call / "raw_response.json").read_bytes())
            fake_qa(work, 2)
            write_review(work, 2)
            incoming = (args.next_dir / "revision_patch.json").read_bytes()
            call2, manifest2 = self.prepare(work, iteration=2)
            self.respond(call2, manifest2, self.response(work, 2))
            completed = self.finalize(work, call2, iteration=2)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertEqual(incoming, (args.next_dir / "revision_patch.json").read_bytes())
            args2 = apply_args(work, 2)
            args2.patch = args2.current_dir / "revision_patch.to-03.json"
            apply_revision(args2)

    def test_canonical_call_record_allows_mixed_sampling_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = self.work(Path(tmp))
            call, manifest = self.prepare(work)
            self.respond(call, manifest, self.response(work))
            record = load_json(call / "call_record.json")
            record["parameter_observations"]["temperature"] = {
                "status": "observed", "value": 0.2, "source": "host_runtime_metadata"}
            record["parameter_observations"]["seed"] = {
                "status": "observed", "value": None, "source": "host_runtime_metadata"}
            atomic_write_json(call / "call_record.json", record)
            completed = self.finalize(work, call)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_canonical_call_record_allows_all_observed_sampling_parameters(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = self.work(Path(tmp))
            call, manifest = self.prepare(work)
            self.respond(call, manifest, self.response(work))
            record = load_json(call / "call_record.json")
            record["parameter_observations"] = {
                name: {"status": "observed", "value": value, "source": "host_runtime_metadata"}
                for name, value in manifest["parameters"].items()
            }
            atomic_write_json(call / "call_record.json", record)
            completed = self.finalize(work, call)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)

    def test_canonical_call_record_rejects_sampling_and_live_evidence_regressions(self):
        cases = ("configured", "unavailable-value", "unavailable-reason", "observed-source", "observed-conflict",
                 "context", "context-placeholder", "parent", "input-order", "input-hash", "image-modality",
                 "response-hash", "response-changed", "downgrade")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                work = self.work(Path(tmp))
                call, manifest = self.prepare(work)
                self.respond(call, manifest, self.response(work))
                record = load_json(call / "call_record.json")
                if case == "configured":
                    record["configured_parameters"]["temperature"] = 0.3
                elif case == "unavailable-value":
                    record["parameter_observations"]["temperature"]["value"] = 0.2
                elif case == "unavailable-reason":
                    record["parameter_observations"]["temperature"]["reason"] = "unknown"
                elif case == "observed-source":
                    record["parameter_observations"]["temperature"] = {"status": "observed", "value": 0.2}
                elif case == "observed-conflict":
                    record["parameter_observations"]["temperature"] = {
                        "status": "observed", "value": 0.3, "source": "host_runtime_metadata"}
                elif case == "context":
                    record["context_evidence"]["context_id"] = "another-context"
                elif case == "context-placeholder":
                    record["context_id"] = "unavailable"
                    record["context_evidence"]["context_id"] = "unavailable"
                elif case == "parent":
                    record["context_evidence"]["parent_context_id"] = "old-context"
                elif case == "input-order":
                    record["delivered_inputs"][0], record["delivered_inputs"][1] = record["delivered_inputs"][1], record["delivered_inputs"][0]
                elif case == "input-hash":
                    record["delivered_inputs"][0]["sha256"] = "0" * 64
                elif case == "image-modality":
                    next(item for item in record["delivered_inputs"] if item["name"] == "source.png")["modality"] = "document"
                elif case == "response-hash":
                    record["raw_response_sha256"] = "0" * 64
                elif case == "response-changed":
                    atomic_write_json(call / "raw_response.json", {"outcome": "changed"})
                elif case == "downgrade":
                    from tests.runtime.test_p3_planner_integration import P3PlannerIntegrationTests
                    P3PlannerIntegrationTests()._record_response(call, manifest, self.response(work))
                    record = load_json(call / "call_record.json")
                    record["iteration"] = manifest["iteration"]
                atomic_write_json(call / "call_record.json", record)
                completed = self.finalize(work, call)
                self.assertNotEqual(0, completed.returncode)
                self.assertFalse(apply_args(work).patch.exists())

    def test_contract_and_response_version_crossing_is_rejected(self):
        for mode in ("cli", "version", "profile"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                work = self.work(Path(tmp))
                call, manifest = self.prepare(work)
                response = self.response(work)
                if mode == "version":
                    response = {"schema_version": "1.4", "task_id": "p5-live-01", "iteration": 1, "mode": "revision", "artifacts": {"review_patch": {}}}
                if mode == "profile":
                    manifest["revision_contract"] = "legacy"
                    atomic_write_json(call / "call_manifest.json", manifest)
                self.respond(call, manifest, response)
                completed = self.finalize(work, call, contract="legacy" if mode == "cli" else "canonical")
                self.assertNotEqual(0, completed.returncode)
                self.assertFalse(apply_args(work).patch.exists())

    def test_legacy_profile_uses_legacy_prompt_and_rejects_canonical_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = self.work(Path(tmp))
            call, manifest = self.prepare(work, contract="legacy")
            self.assertEqual("revision", manifest["input_profile"])
            self.assertEqual(11, len(manifest["inputs"]))
            self.assertIn("artifacts.review_patch", (call / "system_prompt.md").read_text(encoding="utf-8"))
            self.respond(call, manifest, self.response(work))
            self.assertNotEqual(0, self.finalize(work, call, contract="legacy").returncode)

    def test_valid_block_does_not_write_patch_or_iteration(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = self.work(Path(tmp))
            call, manifest = self.prepare(work)
            self.respond(call, manifest, {"schema_version": "1.5", "task_id": "p5-live-01", "iteration": 1, "mode": "revision", "outcome": "block",
                                         "block": {"code": "revision_requires_replan", "scope": "objects", "object_ids": ["card-02"], "message": "broader change required"}})
            completed = self.finalize(work, call)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertFalse(apply_args(work).patch.exists())
            self.assertFalse(apply_args(work).next_dir.exists())

    def test_legacy_finalizer_and_apply_keep_existing_runtime_contract(self):
        from argparse import Namespace
        from asset_common import sha256_file
        from apply_review_patch import apply_patch as legacy_apply
        with tempfile.TemporaryDirectory() as tmp:
            work = self.work(Path(tmp))
            current = apply_args(work).current_dir
            call, manifest = self.prepare(work, contract="legacy")
            patch = {"schema_version": "1.3", "task_id": "p5-live-01", "from_iteration": 1, "to_iteration": 2,
                     "based_on_review_sha256": sha256_file(current / "review_report.json"),
                     "based_on_review_evaluation_sha256": sha256_file(current / "review_evaluation.json"),
                     "preconditions": {key: sha256_file(current / name) for key, name in (("layout_sha256", "layout.json"), ("crops_sha256", "crops.json"), ("asset_manifest_sha256", "asset_manifest.json"))},
                     "operations": [{"issue_id": "issue-01", "type": "update_element", "element_id": "card-02", "changes": {"y": 3.0}}],
                     "preserved_elements": load_json(current / "review_report.json")["approved_elements"]}
            self.respond(call, manifest, {"schema_version": "1.4", "task_id": "p5-live-01", "iteration": 1, "mode": "revision", "artifacts": {"review_patch": patch}})
            completed = self.finalize(work, call, contract="legacy")
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            atomic_write_json(work / "run_state.json", {"schema_version": "1.3", "task_id": "p5-live-01", "request_sha256": sha256_file(work / "request.json"),
                              "state": "review_revise", "current_iteration": 1, "max_iterations": 3, "history": []})
            from tests.runtime.p5_test_support import SCHEMAS
            args = Namespace(work_root=work, run_state=work / "run_state.json", current_dir=current,
                             patch=current / "review_patch.json", next_dir=work / "iterations/02", schema_dir=SCHEMAS)
            legacy_apply(args)
            self.assertEqual("spec_ready", load_json(work / "run_state.json")["state"])
            self.assertFalse((args.next_dir / "reconstruction-plan.json").exists())
