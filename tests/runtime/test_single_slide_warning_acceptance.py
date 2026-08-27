from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"
sys.path.insert(0, str(SCRIPTS))

from asset_common import AssetError, sha256_file
from create_delivery_decision import create_decision
from manage_run_state import warning_response
from package_output import package


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


class SingleSlideWarningAcceptanceTests(unittest.TestCase):
    def _work_root(self, parent: Path) -> tuple[Path, Path]:
        work_root = parent / "work"
        iteration = work_root / "iterations" / "03"
        iteration.mkdir(parents=True)

        request_path = work_root / "request.json"
        _write_json(
            request_path,
            {
                "schema_version": "1.3",
                "task_id": "warning-test",
                "topic": "Warning acceptance",
                "source_image": "source.png",
                "output_ratio": "16:9",
                "typography_interaction": "default",
                "typography": {
                    "title_font": "Arial",
                    "title_size_pt": 28,
                    "body_font": "Arial",
                    "body_size_pt": 16,
                },
                "editability_policy": "text-and-structure",
                "user_requirements": [],
                "review_policy": {
                    "max_iterations": 3,
                    "pass_score": 90,
                    "warning_floor_score": 75,
                    "min_content_accuracy": 90,
                    "required_editability_score": 100,
                    "critical_policy": "by_recoverability",
                },
            },
        )

        qa_path = iteration / "qa_report.json"
        _write_json(
            qa_path,
            {
                "schema_version": "1.3",
                "status": "pass",
                "iteration": 3,
                "hard_failures": [],
                "warnings": [],
                "metrics": {
                    "slide_count": 1,
                    "required_text_count": 1,
                    "editable_required_text_count": 1,
                    "editable_text_ratio": 1,
                    "editable_text_status": "applicable",
                    "missing_required_native_objects": 0,
                    "invalid_text_exemptions": 0,
                    "expected_element_count": 1,
                    "built_element_count": 1,
                    "missing_element_ids": [],
                    "unexpected_element_ids": [],
                    "out_of_bounds_shapes": 0,
                    "missing_media": 0,
                    "font_violations": 0,
                    "rendered_page_count": 1,
                },
                "rendering": {
                    "renderer": "Microsoft PowerPoint",
                    "renderer_version": "test",
                    "fallback_used": False,
                },
                "provenance": {
                    **{key: "0" * 64 for key in (
                        "source_sha256", "request_sha256", "layout_sha256", "crops_sha256",
                        "asset_manifest_sha256", "build_summary_sha256", "ppt_sha256", "render_sha256",
                    )},
                    "skill_version": "1.3",
                    "skill_revision": "test",
                    "builder": "PptxGenJS",
                    "builder_version": "test",
                    "python_version": "test",
                    "pillow_version": "test",
                    "python_pptx_version": "test",
                    "platform": "test",
                    "build_time_utc": "2026-08-27T00:00:00Z",
                },
            },
        )

        check = {"status": "pass", "rationale": "ok", "issue_ids": []}
        agent = {
            "model_selection_mode": "runtime-default",
            "requested_model": None,
            "config_sha256": "0" * 64,
            "prompt_sha256": "0" * 64,
            "temperature": 0,
            "top_p": 1,
            "seed": None,
            "call_id": "call",
            "context_id": "context",
            "parent_context_id": None,
        }
        review_path = iteration / "review_report.json"
        _write_json(
            review_path,
            {
                "schema_version": "1.3",
                "task_id": "warning-test",
                "iteration": 3,
                "reviewer_recommendation": "revise",
                "scores": {
                    "content_accuracy": 95,
                    "layout_similarity": 80,
                    "typography_similarity": 80,
                    "visual_style_similarity": 80,
                    "asset_quality": 90,
                },
                "issues": [],
                "mandatory_visual_checks": {name: check for name in (
                    "connector_topology", "connector_endpoints", "key_proportions", "crop_boundaries",
                    "background_seams", "visual_depth", "typography_hierarchy",
                )},
                "approved_elements": ["title"],
                "warnings": ["minor visual difference"],
                "review_context": {
                    **{key: "0" * 64 for key in (
                        "source_sha256", "render_sha256", "layout_sha256", "qa_report_sha256",
                        "asset_manifest_sha256", "request_sha256", "review_rubric_sha256",
                        "reviewer_response_schema_sha256",
                    )},
                    "reviewer_role_version": "1.3.0",
                },
                "agent_provenance": {
                    "planner": agent,
                    "reviewer": {**agent, "call_id": "review-call", "context_id": "review-context"},
                    "review_rubric_sha256": "0" * 64,
                },
            },
        )

        evaluation_path = iteration / "review_evaluation.json"
        _write_json(
            evaluation_path,
            {
                "schema_version": "1.3",
                "task_id": "warning-test",
                "iteration": 3,
                "reviewer_recommendation": "revise",
                "computed_scores": {
                    "content_accuracy": 95,
                    "layout_similarity": 80,
                    "typography_similarity": 80,
                    "visual_style_similarity": 80,
                    "asset_quality": 90,
                    "editability": 100,
                    "overall_score": 85,
                },
                "issue_counts": {
                    "critical_recoverable": 0,
                    "critical_irrecoverable": 0,
                    "critical_unknown": 0,
                    "major": 0,
                    "minor": 1,
                    "suggestion": 0,
                },
                "failed_visual_checks": [],
                "anchor_consistent": True,
                "score_adjustments": [],
                "policy_decision": "warning_candidate",
                "recommendation_relation": "policy_looser",
                "recommendation_relation_reason": "Final-iteration warning policy applies.",
                "decision_reasons": ["warning_floor_met"],
                "inputs": {
                    "request_sha256": sha256_file(request_path),
                    "qa_report_sha256": sha256_file(qa_path),
                    "review_report_sha256": sha256_file(review_path),
                },
            },
        )

        _write_json(
            work_root / "run_state.json",
            {
                "schema_version": "1.3",
                "task_id": "warning-test",
                "request_sha256": sha256_file(request_path),
                "state": "awaiting_user_acceptance",
                "current_iteration": 3,
                "max_iterations": 3,
                "history": [],
                "pending_decision": {
                    "iteration": 3,
                    "review_evaluation_sha256": sha256_file(evaluation_path),
                    "warnings": ["minor visual difference"],
                },
            },
        )
        return work_root, iteration

    def _respond(self, work_root: Path, decision: str, message: str = "accept") -> dict:
        message_path = work_root / "response.txt"
        with message_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(message)
        return warning_response(
            SimpleNamespace(
                work_root=work_root,
                state=work_root / "run_state.json",
                schema_dir=SCHEMA_DIR,
                decision=decision,
                actor_type="user",
                actor_id=None,
                message_file=message_path,
            )
        )

    def _create_decision(self, work_root: Path, iteration: Path) -> dict:
        return create_decision(
            SimpleNamespace(
                work_root=work_root,
                run_state=work_root / "run_state.json",
                request=work_root / "request.json",
                iteration_dir=iteration,
                output=work_root / "delivery_decision.json",
                schema_dir=SCHEMA_DIR,
            )
        )

    def test_accept_creates_pass_with_warnings_and_enters_packaging(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            work_root, iteration = self._work_root(Path(temp))
            self._respond(work_root, "accept")
            result = self._create_decision(work_root, iteration)

            self.assertEqual(result["status"], "pass_with_warnings")
            state = json.loads((work_root / "run_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["state"], "packaging")

    def test_reject_enters_failed_and_cannot_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            work_root, iteration = self._work_root(Path(temp))
            rejected = self._respond(work_root, "reject")
            self.assertEqual(rejected["state"], "failed")
            self._create_decision(work_root, iteration)

            with self.assertRaisesRegex(AssetError, "delivery gate"):
                package(
                    SimpleNamespace(
                        work_root=work_root,
                        run_state=work_root / "run_state.json",
                        delivery_decision=work_root / "delivery_decision.json",
                        ppt=iteration / "slide.pptx",
                        dist_root=Path(temp) / "dist",
                        output_name="warning-test",
                        schema_dir=SCHEMA_DIR,
                    )
                )

    def test_stale_evaluation_hash_rejects_decision_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            work_root, iteration = self._work_root(Path(temp))
            self._respond(work_root, "accept")
            evaluation_path = iteration / "review_evaluation.json"
            evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
            evaluation["decision_reasons"] = ["warning_floor_met", "changed_after_acceptance"]
            _write_json(evaluation_path, evaluation)

            with self.assertRaisesRegex(AssetError, "stale"):
                self._create_decision(work_root, iteration)
            self.assertFalse((work_root / "delivery_decision.json").exists())

    def test_message_is_normalized_and_only_its_hash_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            work_root, _ = self._work_root(Path(temp))
            raw_message = "Cafe\u0301\r\n同意\r"
            state = self._respond(work_root, "accept", raw_message)
            expected = hashlib.sha256("Café\n同意\n".encode("utf-8")).hexdigest()

            self.assertEqual(state["acceptance"]["message_sha256"], expected)
            serialized = (work_root / "run_state.json").read_text(encoding="utf-8")
            self.assertNotIn("Cafe", serialized)
            self.assertNotIn("Café", serialized)
            self.assertNotIn("同意", serialized)


if __name__ == "__main__":
    unittest.main()
