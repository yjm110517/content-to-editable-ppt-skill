from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from canonical_artifact import canonical_sha256
from deterministic_project_slide_content import build_projection
from markdown_wireframe import build_validation_report, load_markdown_authority
from tests.runtime.test_p2_markdown_binder import NOW, H, approved, candidate


class P2MarkdownWorkflowTests(unittest.TestCase):
    def prepare(self, root: Path) -> dict[str, Path]:
        outline = approved(); slides, projection = build_projection(outline, frozen_at_utc=NOW)
        state = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "task_id": "task-1", "deck_id": "D01", "state": "p1_complete", "counters": {"host_planning_pass_count": 1, "host_revision_pass_count": 0, "automatic_regeneration_count": 0, "planner_calls": 0, "reviewer_calls": 0}, "current_artifacts": {"task_route_sha256": None, "materials_sha256": None, "candidate_outline_sha256": None, "confirmation_sha256": None, "approved_outline_sha256": canonical_sha256(outline), "slide_content_manifest_sha256": canonical_sha256(projection)}, "history": []}
        paths = {"p1": root / "p1.json", "outline": root / "outline.json", "content": root / "content", "candidate": root / "candidate.json", "state": root / "p2-state.json", "wireframes": root / "wireframes", "report": root / "report.json"}
        paths["content"].mkdir()
        for slide, item in zip(slides, projection["slides"]):
            (paths["content"] / item["path"]).write_text(json.dumps(slide, ensure_ascii=False), encoding="utf-8")
        (paths["content"] / "projection-manifest.json").write_text(json.dumps(projection, ensure_ascii=False), encoding="utf-8")
        for key, value in (("p1", state), ("outline", outline), ("candidate", candidate())):
            paths[key].write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return paths

    def run_cli(self, *args: object, expect: int = 0) -> dict:
        result = subprocess.run([sys.executable, str(SCRIPTS / "manage_wireframe.py"), *(str(arg) for arg in args)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def reach_preview(self, paths: dict[str, Path]) -> dict:
        self.run_cli("init", "--task-id", "task-1", "--p1-state", paths["p1"], "--approved-outline", paths["outline"], "--slide-content-dir", paths["content"], "--wireframe-root", paths["wireframes"], "--state", paths["state"])
        self.run_cli("submit-candidate", "--state", paths["state"], "--candidate", paths["candidate"], "--approved-outline", paths["outline"], "--slide-content-dir", paths["content"], "--validation-report", paths["report"])
        result = self.run_cli("bind", "--state", paths["state"], "--candidate", paths["candidate"], "--approved-outline", paths["outline"], "--slide-content-dir", paths["content"], "--wireframe-root", paths["wireframes"])
        self.assertEqual(result["state"], "ready_for_preview")
        return json.loads((paths["wireframes"] / "revisions" / "r001" / "preview-manifest.json").read_text(encoding="utf-8"))

    def feedback(self, paths: dict[str, Path], manifest: dict, *, decision: str, scope: str, slides: list[str]) -> Path:
        state = json.loads(paths["state"].read_text(encoding="utf-8"))
        document = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_type": "markdown_wireframe_feedback", "feedback_id": "f1", "deck_id": "D01", "revision": 1, "wireframe_manifest_sha256": canonical_sha256(manifest), "preview_sha256": state["current_artifacts"]["preview_sha256"], "decision": decision, "change_scope": scope, "affected_slide_ids": slides, "user_message_sha256": H, "created_at_utc": NOW}
        target = paths["wireframes"].parent / "feedback-input.json"; target.write_text(json.dumps(document), encoding="utf-8"); return target

    def test_user_visible_continue_publishes_current_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.prepare(Path(temporary)); manifest = self.reach_preview(paths)
            self.run_cli("record-preview", "--state", paths["state"], "--wireframe-root", paths["wireframes"], "--mode", "user_visible", "--user-message-sha256", H)
            feedback = self.feedback(paths, manifest, decision="continue", scope="none", slides=[])
            result = self.run_cli("record-feedback", "--state", paths["state"], "--wireframe-root", paths["wireframes"], "--feedback", feedback)
            self.assertEqual(result["state"], "p2_complete")
            self.assertTrue((paths["wireframes"] / "deck-wireframe.md").is_file())
            self.run_cli("verify", "--state", paths["state"], "--approved-outline", paths["outline"], "--slide-content-dir", paths["content"], "--wireframe-root", paths["wireframes"])
            accepted = paths["wireframes"] / "revisions" / "r001" / "wireframe-manifest.json"
            top = paths["wireframes"] / "wireframe-manifest.json"
            self.assertEqual(accepted.read_bytes(), top.read_bytes())

    def test_skip_requires_message_and_completes_without_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.prepare(Path(temporary)); self.reach_preview(paths)
            result = self.run_cli("record-preview", "--state", paths["state"], "--wireframe-root", paths["wireframes"], "--mode", "skipped", "--user-message-sha256", H)
            self.assertEqual(result["state"], "p2_complete")

    def test_layout_and_content_feedback_route_separately(self) -> None:
        for scope, expected in (("layout", "revision_requested"), ("content", "p1_revision_required")):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as temporary:
                paths = self.prepare(Path(temporary)); manifest = self.reach_preview(paths)
                self.run_cli("record-preview", "--state", paths["state"], "--wireframe-root", paths["wireframes"], "--mode", "user_visible", "--user-message-sha256", H)
                feedback = self.feedback(paths, manifest, decision="changes_requested", scope=scope, slides=["S01"])
                result = self.run_cli("record-feedback", "--state", paths["state"], "--wireframe-root", paths["wireframes"], "--feedback", feedback)
                self.assertEqual(result["state"], expected)

    def test_stale_feedback_and_authority_tamper_preserve_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.prepare(Path(temporary)); manifest = self.reach_preview(paths)
            self.run_cli("record-preview", "--state", paths["state"], "--wireframe-root", paths["wireframes"], "--mode", "user_visible", "--user-message-sha256", H)
            feedback_path = self.feedback(paths, manifest, decision="continue", scope="none", slides=[])
            feedback = json.loads(feedback_path.read_text()); feedback["preview_sha256"] = "b" * 64; feedback_path.write_text(json.dumps(feedback))
            before = paths["state"].read_bytes()
            self.run_cli("record-feedback", "--state", paths["state"], "--wireframe-root", paths["wireframes"], "--feedback", feedback_path, expect=4)
            self.assertEqual(before, paths["state"].read_bytes())
            outline = json.loads(paths["outline"].read_text(encoding="utf-8")); outline["artifact_id"] = "tampered"; paths["outline"].write_text(json.dumps(outline))
            self.run_cli("verify", "--state", paths["state"], "--approved-outline", paths["outline"], "--slide-content-dir", paths["content"], "--wireframe-root", paths["wireframes"], expect=4)

    def test_revision_artifacts_refuse_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.prepare(Path(temporary)); self.reach_preview(paths); before = paths["state"].read_bytes()
            self.run_cli("bind", "--state", paths["state"], "--candidate", paths["candidate"], "--approved-outline", paths["outline"], "--slide-content-dir", paths["content"], "--wireframe-root", paths["wireframes"], expect=4)
            self.assertEqual(before, paths["state"].read_bytes())

    def test_correction_requires_issue_binding_before_value_and_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.prepare(Path(temporary))
            self.run_cli("init", "--task-id", "task-1", "--p1-state", paths["p1"], "--approved-outline", paths["outline"], "--slide-content-dir", paths["content"], "--wireframe-root", paths["wireframes"], "--state", paths["state"])
            invalid = candidate(); invalid["slides"][0]["content_labels"][1]["label"] = "错误标签"
            paths["candidate"].write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
            result = self.run_cli("submit-candidate", "--state", paths["state"], "--candidate", paths["candidate"], "--approved-outline", paths["outline"], "--slide-content-dir", paths["content"], "--validation-report", paths["report"])
            self.assertEqual(result["validation_status"], "correctable")
            report = json.loads(paths["report"].read_text(encoding="utf-8")); issue = next(item for item in report["issues"] if item["code"] == "label_not_authority_substring")
            correction = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_type": "markdown_wireframe_correction_record", "correction_id": "c1", "deck_id": "D01", "attempt": 1, "host_model_invocation_id": "h2", "candidate_sha256": canonical_sha256(invalid), "validation_report_sha256": canonical_sha256(report), "operations": [{"op": "replace", "validation_issue_id": issue["issue_id"], "path": "/slides/0/content_labels/1/label", "before": "错误标签", "after": "即时反馈"}], "created_at_utc": NOW}
            correction_path, output = Path(temporary) / "correction.json", Path(temporary) / "corrected.json"
            correction_path.write_text(json.dumps(correction, ensure_ascii=False), encoding="utf-8")
            self.run_cli("apply-correction", "--state", paths["state"], "--candidate", paths["candidate"], "--validation-report", paths["report"], "--correction", correction_path, "--output", output)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["slides"][0]["content_labels"][1]["label"], "即时反馈")
            stale = dict(correction); stale["correction_id"] = "c2"; stale["host_model_invocation_id"] = "h3"; stale["operations"] = [dict(correction["operations"][0], before="其他")]
            stale_path = Path(temporary) / "stale.json"; stale_path.write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")
            before_state = paths["state"].read_bytes()
            self.run_cli("apply-correction", "--state", paths["state"], "--candidate", paths["candidate"], "--validation-report", paths["report"], "--correction", stale_path, "--output", Path(temporary) / "bad.json", expect=4)
            self.assertEqual(before_state, paths["state"].read_bytes())


if __name__ == "__main__":
    unittest.main()
