from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from markdown_wireframe import audit_markdown, bind_markdown, build_validation_report, sha256_bytes
from schema_utils import ContractError, validate_schema
from tests.runtime.test_p2_markdown_binder import MarkdownWireframeBinderTests, NOW, candidate


def storyboard_candidate() -> dict:
    document = candidate()
    document["schema_version"] = "1.2"
    visual = document["slides"][0]["visual_placeholders"][0]
    visual.update({
        "placement": {"region": "center", "prominence": "primary"},
        "storyboard": [
            {"beat_id": "B01", "action": "show_sequence", "source_ref": "S01-TITLE", "focus_phrase": "生成式AI"},
            {"beat_id": "B02", "action": "show_relationship", "source_ref": "S01-TITLE", "focus_phrase": "支持学习"},
        ],
        "reading_order": ["B01", "B02"],
    })
    return document


class P2VisualStoryboardTests(unittest.TestCase):
    def bundle(self, root: Path) -> dict:
        return MarkdownWireframeBinderTests().bundle(root)

    def test_valid_storyboard_binds_visible_position_content_and_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(Path(temporary))
            document = storyboard_candidate()
            report = build_validation_report(document, bundle, report_id="storyboard", validated_at_utc=NOW)
            self.assertEqual(report["status"], "pass")
            markdown, manifest = bind_markdown(document, bundle)
            text = markdown.decode("utf-8")
            self.assertIn("### 视觉分镜", text)
            self.assertIn("位置：中央；层级：主视觉", text)
            self.assertLess(text.index("B01｜呈现序列"), text.index("B02｜呈现关系"))
            self.assertEqual(manifest["schema_version"], "1.2")
            tampered = markdown.replace("呈现序列".encode("utf-8"), "呈现轨迹".encode("utf-8"))
            tampered_manifest = copy.deepcopy(manifest); tampered_manifest["wireframe_sha256"] = sha256_bytes(tampered)
            with self.assertRaises(ContractError):
                audit_markdown(tampered, tampered_manifest, bundle)

    def test_missing_duplicate_order_and_unknown_action_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(Path(temporary))
            missing = storyboard_candidate(); missing["slides"][0]["visual_placeholders"][0].pop("storyboard")
            self.assertIn("storyboard_missing", {item["code"] for item in build_validation_report(missing, bundle, report_id="m", validated_at_utc=NOW)["issues"]})
            duplicate = storyboard_candidate(); duplicate["slides"][0]["visual_placeholders"][0]["storyboard"][1]["beat_id"] = "B01"
            self.assertIn("duplicate_storyboard_beat", {item["code"] for item in build_validation_report(duplicate, bundle, report_id="d", validated_at_utc=NOW)["issues"]})
            wrong_order = storyboard_candidate(); wrong_order["slides"][0]["visual_placeholders"][0]["reading_order"] = ["B02", "B01"]
            self.assertIn("storyboard_order_mismatch", {item["code"] for item in build_validation_report(wrong_order, bundle, report_id="o", validated_at_utc=NOW)["issues"]})
            unknown = storyboard_candidate(); unknown["slides"][0]["visual_placeholders"][0]["storyboard"][0]["action"] = "draw_robot"
            with self.assertRaises(ContractError):
                validate_schema("markdown_wireframe_candidate", unknown, ROOT / "content-to-editable-ppt" / "schemas")

    def test_storyboard_source_phrase_and_asset_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = self.bundle(Path(temporary))
            cross = storyboard_candidate(); cross["slides"][0]["visual_placeholders"][0]["storyboard"][0]["source_ref"] = "S01-C01"
            self.assertIn("storyboard_source_not_bound", {item["code"] for item in build_validation_report(cross, bundle, report_id="s", validated_at_utc=NOW)["issues"]})
            invented = storyboard_candidate(); invented["slides"][0]["visual_placeholders"][0]["storyboard"][0]["focus_phrase"] = "机器人教师"
            self.assertIn("storyboard_phrase_not_authority_substring", {item["code"] for item in build_validation_report(invented, bundle, report_id="p", validated_at_utc=NOW)["issues"]})
            concrete = storyboard_candidate(); concrete["slides"][0]["visual_placeholders"][0]["storyboard"][0]["focus_phrase"] = "Tabler.svg"
            report = build_validation_report(concrete, bundle, report_id="a", validated_at_utc=NOW)
            self.assertIn("concrete_asset_forbidden", {item["code"] for item in report["issues"]})

    def test_legacy_1_1_remains_valid_historical_contract(self) -> None:
        validate_schema("markdown_wireframe_candidate", candidate(), ROOT / "content-to-editable-ppt" / "schemas")


if __name__ == "__main__":
    unittest.main()
