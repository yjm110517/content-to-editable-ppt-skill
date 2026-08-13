from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from canonical_artifact import canonical_sha256
from deterministic_project_slide_content import build_projection
from markdown_wireframe import audit_markdown, bind_markdown, build_validation_report, load_markdown_authority
from schema_utils import ContractError, validate_schema


NOW = "2026-08-13T00:00:00Z"
H = "a" * 64


def page() -> dict:
    return {
        "slide_id": "S01", "order": 1, "role": "content", "purpose": "explain",
        "key_message": "即时反馈支持学习", "title": {"content_ref": "S01-TITLE", "text": "生成式AI如何支持学习"},
        "content_blocks": [{"content_ref": "S01-C01", "order": 1, "text": "提供即时反馈与个性化支持", "source_refs": ["M01-F01"]}],
        "visual_intent": "two ideas", "source_refs": ["M01-F01"],
    }


def approved() -> dict:
    return {
        "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1",
        "artifact_id": "outline-1", "deck_id": "D01", "revision": 1, "parent_sha256": None,
        "candidate_revision": 1, "candidate_sha256": H, "confirmation_id": "confirm-1",
        "confirmation_sha256": H, "pages": [page()], "approved_at_utc": NOW,
    }


def candidate() -> dict:
    return {
        "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1",
        "artifact_type": "markdown_wireframe_candidate", "artifact_id": "wf-candidate-1",
        "deck_id": "D01", "revision": 1, "parent_sha256": None, "pass_id": "initial",
        "host_model_invocation_id": "host-1",
        "slides": [{
            "slide_id": "S01", "order": 1,
            "layout_draft": "┌──{{p2:content-ref=S01-TITLE}}──┐\n│ {{p2:zone=diagram}} │\n└──{{p2:content-ref=S01-C01}}──┘",
            "content_labels": [
                {"content_ref": "S01-TITLE", "label": "生成式AI如何支持学习"},
                {"content_ref": "S01-C01", "label": "即时反馈"},
            ],
            "layout_notes": "标题置顶，正文位于图示下方，阅读顺序由上到下。",
        }],
        "created_at_utc": NOW,
    }


class MarkdownWireframeBinderTests(unittest.TestCase):
    def authority_paths(self, root: Path) -> dict[str, Path]:
        outline = approved()
        slides, projection = build_projection(outline, frozen_at_utc=NOW)
        state = {
            "schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1",
            "task_id": "task-1", "deck_id": "D01", "state": "p1_complete",
            "counters": {"host_planning_pass_count": 1, "host_revision_pass_count": 0,
                         "automatic_regeneration_count": 0, "planner_calls": 0, "reviewer_calls": 0},
            "current_artifacts": {"task_route_sha256": None, "materials_sha256": None,
                                  "candidate_outline_sha256": None, "confirmation_sha256": None,
                                  "approved_outline_sha256": canonical_sha256(outline),
                                  "slide_content_manifest_sha256": canonical_sha256(projection)},
            "history": [],
        }
        content_dir = root / "slide-content"
        content_dir.mkdir()
        for slide, item in zip(slides, projection["slides"]):
            (content_dir / item["path"]).write_text(json.dumps(slide, ensure_ascii=False, indent=2), encoding="utf-8")
        (content_dir / "projection-manifest.json").write_text(json.dumps(projection, ensure_ascii=False, indent=2), encoding="utf-8")
        state_path, outline_path = root / "state.json", root / "approved-outline.json"
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        outline_path.write_text(json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"state": state_path, "outline": outline_path, "content": content_dir}

    def bundle(self, root: Path) -> dict:
        paths = self.authority_paths(root)
        return load_markdown_authority(
            p1_state_path=paths["state"], approved_outline_path=paths["outline"], slide_content_dir=paths["content"]
        )

    def test_schema_and_valid_candidate_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(Path(temporary))
            document = candidate()
            validate_schema("markdown_wireframe_candidate", document, ROOT / "content-to-editable-ppt" / "schemas")
            report = build_validation_report(document, bundle, report_id="report-1", validated_at_utc=NOW)
            self.assertEqual(report["status"], "pass")
            validate_schema("markdown_wireframe_validation_report", report, ROOT / "content-to-editable-ppt" / "schemas")

    def test_authority_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.authority_paths(Path(temporary))
            outline = json.loads(paths["outline"].read_text(encoding="utf-8"))
            outline["pages"][0]["title"]["text"] = "篡改"
            paths["outline"].write_text(json.dumps(outline, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ContractError) as raised:
                load_markdown_authority(p1_state_path=paths["state"], approved_outline_path=paths["outline"], slide_content_dir=paths["content"])
            self.assertIn("authority_hash_mismatch", {item["code"] for item in raised.exception.errors})

    def test_label_must_be_continuous_authority_substring(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(Path(temporary))
            document = candidate()
            document["slides"][0]["content_labels"][1]["label"] = "全新宣传语"
            report = build_validation_report(document, bundle, report_id="r", validated_at_utc=NOW)
            self.assertEqual(report["status"], "correctable")
            self.assertIn("label_not_authority_substring", {item["code"] for item in report["issues"]})

    def test_missing_unknown_and_free_copy_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(Path(temporary))
            missing = candidate()
            missing["slides"][0]["layout_draft"] = missing["slides"][0]["layout_draft"].replace("{{p2:content-ref=S01-C01}}", "")
            self.assertIn("content_placeholder_sequence_mismatch", {item["code"] for item in build_validation_report(missing, bundle, report_id="m", validated_at_utc=NOW)["issues"]})
            unknown = candidate()
            unknown["slides"][0]["layout_draft"] += "{{p2:zone=video}}"
            self.assertIn("unknown_placeholder", {item["code"] for item in build_validation_report(unknown, bundle, report_id="u", validated_at_utc=NOW)["issues"]})
            copy_candidate = candidate()
            copy_candidate["slides"][0]["layout_draft"] += "新增文案"
            self.assertIn("free_page_copy", {item["code"] for item in build_validation_report(copy_candidate, bundle, report_id="c", validated_at_utc=NOW)["issues"]})

    def test_binder_is_byte_deterministic_and_contains_full_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(Path(temporary))
            first, first_manifest = bind_markdown(candidate(), bundle)
            second, second_manifest = bind_markdown(candidate(), bundle)
            self.assertEqual(first, second)
            self.assertEqual(first_manifest, second_manifest)
            text = first.decode("utf-8")
            self.assertIn("提供即时反馈与个性化支持", text)
            self.assertIn("<!-- p2:content-ref=S01-C01:start -->", text)
            validate_schema("markdown_wireframe_manifest", first_manifest, ROOT / "content-to-editable-ppt" / "schemas")

    def test_visible_authority_and_metadata_tamper_fail_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(Path(temporary))
            markdown, manifest = bind_markdown(candidate(), bundle)
            for before, after in (("提供即时反馈与个性化支持", "提供错误内容"), ("S01-C01:start", "S01-C99:start")):
                tampered = markdown.decode("utf-8").replace(before, after).encode("utf-8")
                tampered_manifest = copy.deepcopy(manifest)
                from markdown_wireframe import sha256_bytes
                tampered_manifest["wireframe_sha256"] = sha256_bytes(tampered)
                with self.assertRaises(ContractError):
                    audit_markdown(tampered, tampered_manifest, bundle)

    def test_candidate_markup_and_external_reference_are_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(Path(temporary))
            for injected in ("<!-- p2:slide-id=X -->", "https://example.com", "```", "<script>"):
                document = candidate()
                document["slides"][0]["layout_notes"] += injected
                report = build_validation_report(document, bundle, report_id="unsafe", validated_at_utc=NOW)
                self.assertEqual(report["status"], "blocking")
                self.assertIn("unsafe_candidate_text", {item["code"] for item in report["issues"]})


if __name__ == "__main__":
    unittest.main()
