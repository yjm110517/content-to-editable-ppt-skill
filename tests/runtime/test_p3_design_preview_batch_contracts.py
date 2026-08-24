from __future__ import annotations

import sys
import json
import hashlib
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from canonical_artifact import canonical_sha256  # noqa: E402
from design_preview_batch import initial_state, refresh_state, update_page, validate_map_evidence  # noqa: E402
from schema_utils import ContractError, validate_schema  # noqa: E402


H = "a" * 64


class DesignPreviewBatchContractsTests(unittest.TestCase):
    def state(self, count: int = 3) -> dict:
        slides = [{"slide_id": f"S{index:02d}", "order": index} for index in range(1, count + 1)]
        return initial_state(deck_id="D01", slides=slides, anchor_slide_id="S02", artifacts={"style_anchor_record_sha256": H, "deck_prompt_package_sha256": H})

    def test_initial_state_imports_anchor_and_marks_remaining_pages_generated(self) -> None:
        value = self.state()
        self.assertEqual(value["state"], "anchor_approved")
        self.assertEqual([item["status"] for item in value["pages"]], ["generated", "anchor_approved", "generated"])

    def test_page_progress_is_hash_bound_and_resumable(self) -> None:
        value = update_page(self.state(), "S01", status="map_package_ready", generated_layer_record_sha256=H, map_input_manifest_sha256="b" * 64)
        self.assertEqual(refresh_state(value)["state"], "map_evidence_required")
        value = update_page(value, "S01", status="rendered", map_call_record_sha256="c" * 64, element_map_sha256="d" * 64, compatibility_report_sha256="e" * 64, final_preview_record_sha256="f" * 64)
        value = update_page(value, "S03", status="rendered", generated_layer_record_sha256=H, map_call_record_sha256="c" * 64, element_map_sha256="d" * 64, compatibility_report_sha256="e" * 64, final_preview_record_sha256="f" * 64)
        self.assertEqual(refresh_state(value)["state"], "contact_sheet_ready")

    def test_unknown_slide_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            update_page(self.state(), "S99", status="failed", error_code="missing")

    def test_schema_rejects_cross_page_status_shape(self) -> None:
        value = self.state()
        value["pages"][0]["status"] = "made_up"
        with self.assertRaises(ContractError):
            validate_schema("design_preview_batch_state", value, ROOT / "content-to-editable-ppt" / "schemas")

    def test_map_evidence_binds_every_input_and_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); inputs = root / "inputs"; inputs.mkdir()
            names = ["generated-layer.png", "prompt-package.json", "element-intents.json", "slide-content.json", "visual-system.json", "design-element-map.schema.json"]
            entries = []
            for name in names:
                path = inputs / name; path.write_bytes(name.encode("utf-8")); entries.append({"name": name, "filename": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "media_type": "application/json", "purpose": "map_input"})
            manifest = {"schema_version": "1.0", "artifact_type": "design_element_map_input_manifest", "deck_id": "D01", "slide_id": "S01", "prompt_package_sha256": H, "generated_layer_sha256": "b" * 64, "inputs": entries}
            mapping = {"schema_version": "1.0", "artifact_type": "design_element_map", "deck_id": "D01", "slide_id": "S01", "generated_layer_sha256": "b" * 64, "prompt_package_sha256": H, "elements": [{"element_id": "EL-S01-TITLE", "source_ref": "S01-TITLE", "element_owner": "deterministic_compositor", "reconstruction_class": "native_text", "editable_required": True, "fidelity_priority": "critical", "p4_strategy": "reuse_authority_text_spec", "normalized_bbox": {"x": 500, "y": 500, "w": 3000, "h": 1000}, "z_index": 20, "relationship_refs": []}], "forbidden_generated_content": {"text_like_marks": False, "logo_like_marks": False, "unauthorized_labels": False, "duplicate_resolved_icons": False, "duplicate_chart_content": False, "unclassified_major_visual_count": 0}, "full_raw_layer_reuse_allowed": False, "host_map_pass_count": 1, "map_correction_count": 0, "status": "submitted"}
            raw = json.dumps(mapping, ensure_ascii=False).encode("utf-8")
            (root / "map-input-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "raw_response.json").write_bytes(raw)
            (root / "finalized-element-map.json").write_text(json.dumps(mapping), encoding="utf-8")
            record = {"schema_version": "1.0", "artifact_type": "design_element_map_call_record", "call_id": "map-1", "deck_id": "D01", "slide_id": "S01", "map_input_manifest_sha256": canonical_sha256(manifest), "generated_layer_sha256": "b" * 64, "prompt_package_sha256": H, "raw_response_sha256": hashlib.sha256(raw).hexdigest(), "finalized_element_map_sha256": canonical_sha256(mapping), "model_selection_mode": "runtime-default", "requested_model": None, "context_id": "fresh-map-context", "parent_context_id": None, "technical_retry_count": 0, "map_correction_count": 0, "status": "succeeded", "prepared_at_utc": "2026-08-24T00:00:00Z", "invoked_at_utc": "2026-08-24T00:00:01Z", "completed_at_utc": "2026-08-24T00:00:02Z"}
            (root / "call-record.json").write_text(json.dumps(record), encoding="utf-8")
            self.assertEqual(validate_map_evidence(root, deck_id="D01", slide_id="S01", generated_layer_sha256="b" * 64, prompt_package_sha256=H)["record"]["call_id"], "map-1")
            (inputs / "slide-content.json").write_text("tampered", encoding="utf-8")
            with self.assertRaises(ContractError):
                validate_map_evidence(root, deck_id="D01", slide_id="S01", generated_layer_sha256="b" * 64, prompt_package_sha256=H)


if __name__ == "__main__":
    unittest.main()
