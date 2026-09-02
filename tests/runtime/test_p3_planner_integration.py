from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
SCHEMAS = ROOT / "content-to-editable-ppt" / "schemas"
sys.path.insert(0, str(SCRIPTS))

from asset_common import atomic_write_json, sha256_file
from finalize_agent_response import _finalize_initial
from materialize_reconstruction_handoff import materialize_handoff
from tests.runtime.handoff_test_support import materializer_args
from tests.runtime.test_visual_first_planner import handoff as supported_handoff
from tests.runtime.test_visual_first_planner import plan as supported_plan


class P3PlannerIntegrationTests(unittest.TestCase):
    def _materialized_work(self, root: Path) -> Path:
        args = materializer_args(root, SCHEMAS, sha256_file)
        materialize_handoff(args)
        return args.work_root

    def test_prepare_initial_call_uses_exact_p3_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = self._materialized_work(Path(tmp))
            call_dir = work / ".agent-calls" / "01" / "planner" / "p3-call"
            command = [
                sys.executable, str(SCRIPTS / "prepare_agent_call.py"),
                "--role", "planner", "--mode", "initial",
                "--work-root", str(work), "--request", str(work / "request.json"),
                "--source", str(work / "source.png"),
                "--reconstruction-handoff", str(work / "reconstruction-handoff.json"),
                "--slide-id", "S01", "--iteration", "1", "--call-id", "p3-call",
                "--output-dir", str(call_dir), "--schema-dir", str(SCHEMAS),
            ]
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            names = {item.name for item in (call_dir / "inputs").iterdir()}
            self.assertEqual({
                "request.json", "source.png", "reconstruction-handoff.json", "visual-spec.json",
                "reconstruction-plan.schema.json", "element-classification.md", "planner-response.schema.json",
            }, names)
            self.assertNotIn("source-content.json", names)
            manifest = json.loads((call_dir / "call_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("S01", manifest["slide_id"])

            input_sha256 = {item["name"]: item["sha256"] for item in manifest["inputs"]}
            record = {
                "schema_version": "1.3", "task_id": manifest["task_id"], "iteration": 1,
                "role": "planner", "role_version": manifest["role_version"],
                "model_selection_mode": manifest["model_selection_mode"], "requested_model": manifest["requested_model"],
                "config_sha256": manifest["config_sha256"], "prompt_sha256": manifest["prompt_sha256"],
                "output_schema_sha256": manifest["output_schema_sha256"], "input_sha256": input_sha256,
                "parameters": manifest["parameters"], "call_id": manifest["call_id"],
                "context_id": "fixture-context", "parent_context_id": None, "status": "succeeded",
            }
            atomic_write_json(call_dir / "call_record.json", record)
            atomic_write_json(call_dir / "raw_response.json", {
                "schema_version": "1.4", "task_id": manifest["task_id"], "iteration": 1,
                "mode": "initial", "outcome": "block",
                "block": {"code": "unsupported_reconstruction", "scope": "objects", "object_ids": ["chart-01", "table-01"], "message": "Native chart and table reconstruction requires P4"},
            })
            output = work / "iterations" / "01"
            finalized = subprocess.run([
                sys.executable, str(SCRIPTS / "finalize_agent_response.py"),
                "--role", "planner", "--mode", "initial", "--call-dir", str(call_dir),
                "--output-dir", str(output), "--run-id", "p3-fixture", "--iteration", "1",
                "--schema-dir", str(SCHEMAS),
            ], capture_output=True, text=True)
            self.assertEqual(0, finalized.returncode, finalized.stderr or finalized.stdout)
            self.assertFalse(output.exists())
            self.assertEqual("blocked", json.loads(finalized.stdout)["outputs"]["planner_status"])

    def test_prepare_rejects_visual_spec_changed_after_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = self._materialized_work(Path(tmp))
            (work / "visual-spec.json").write_text("{}", encoding="utf-8")
            call_dir = work / ".agent-calls" / "01" / "planner" / "tampered"
            completed = subprocess.run([
                sys.executable, str(SCRIPTS / "prepare_agent_call.py"),
                "--role", "planner", "--mode", "initial", "--work-root", str(work),
                "--request", str(work / "request.json"), "--source", str(work / "source.png"),
                "--reconstruction-handoff", str(work / "reconstruction-handoff.json"), "--slide-id", "S01",
                "--iteration", "1", "--call-id", "tampered", "--output-dir", str(call_dir),
                "--schema-dir", str(SCHEMAS),
            ], capture_output=True, text=True)
            self.assertEqual(9, completed.returncode)
            self.assertEqual("visual_spec_changed", json.loads(completed.stdout)["error"]["category"])
            self.assertFalse(call_dir.exists())

    def test_finalizer_plan_compiles_four_iteration_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            (work / "iterations").mkdir(parents=True)
            request = {
                "schema_version": "1.3", "task_id": "p3-task", "topic": "P3", "source_image": "source.png",
                "output_ratio": "16:9", "typography_interaction": "default",
                "typography": {"title_font": "Microsoft YaHei", "title_size_pt": 28, "body_font": "Microsoft YaHei", "body_size_pt": 16},
                "editability_policy": "text-and-structure", "user_requirements": [],
                "review_policy": {"max_iterations": 1, "pass_score": 90, "warning_floor_score": 85, "min_content_accuracy": 98, "required_editability_score": 100, "critical_policy": "by_recoverability"},
            }
            current_handoff = supported_handoff()
            content = {"text_items": [{"id": "title-content", "text": "Canonical Plan"}]}
            atomic_write_json(work / "request.json", request)
            atomic_write_json(work / "source-content.json", content)
            atomic_write_json(work / "reconstruction-handoff.json", current_handoff)
            (work / "visual-spec.json").write_text("{}", encoding="utf-8")
            Image.new("RGB", (1600, 900), "#DDEEFF").save(work / "source.png")

            call_dir = work / ".agent-calls" / "01" / "planner" / "fixture"
            (call_dir / "inputs").mkdir(parents=True)
            atomic_write_json(call_dir / "inputs" / "request.json", request)
            atomic_write_json(call_dir / "inputs" / "reconstruction-handoff.json", current_handoff)
            output = work / "iterations" / "01"
            args = argparse.Namespace(output_dir=output, call_dir=call_dir, schema_dir=SCHEMAS, iteration=1)
            response = {"outcome": "plan", "artifacts": {"reconstruction_plan": supported_plan()}}
            result = _finalize_initial(args, {"slide_id": "S01"}, response)
            self.assertEqual("planned", result["planner_status"])
            self.assertEqual({"reconstruction-plan.json", "layout.json", "crops.json", "asset_manifest.json"}, {item.name for item in output.iterdir()})
            layout = json.loads((output / "layout.json").read_text(encoding="utf-8"))
            self.assertEqual("Canonical Plan", next(item["text"] for item in layout["elements"] if item["type"] == "text"))

    def test_finalizer_block_is_successful_without_iteration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            (work / "iterations").mkdir(parents=True)
            call_dir = work / ".agent-calls" / "01" / "planner" / "fixture"
            (call_dir / "inputs").mkdir(parents=True)
            atomic_write_json(call_dir / "inputs" / "request.json", {"source_image": "source.png"})
            atomic_write_json(call_dir / "inputs" / "reconstruction-handoff.json", supported_handoff())
            output = work / "iterations" / "01"
            args = argparse.Namespace(output_dir=output, call_dir=call_dir, schema_dir=SCHEMAS, iteration=1)
            block = {"code": "authority_conflict", "scope": "page", "message": "page-wide conflict"}
            result = _finalize_initial(args, {"slide_id": "S01"}, {"outcome": "block", "block": block})
            self.assertEqual("blocked", result["planner_status"])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
