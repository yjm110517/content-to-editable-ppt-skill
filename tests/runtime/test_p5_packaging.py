from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys_path = str(ROOT / "content-to-editable-ppt" / "scripts")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from p5_atomic import p5_canonical_bytes, write_once_p5_artifact  # noqa: E402
from packaging_runtime import build_package_candidate, file_sha256, lock_packaging_runtime, package_formal_delivery, verify_delivery  # noqa: E402
from schema_utils import ContractError, load_json  # noqa: E402


def _fixture(root: Path) -> dict:
    def write(name: str, payload: bytes) -> Path:
        path = root / name
        path.write_bytes(payload)
        return path

    candidate = write("candidate.pptx", b"PK fake pptx bytes")
    qa = write("qa.json", p5_canonical_bytes({"schema_version": "1.0", "artifact_type": "deck_final_qa_report", "deck_id": "D05", "status": "pass", "blocking_issues": 0, "content_drift": 0, "chart_drift": 0, "asset_drift": 0, "checks": [], "issues": [], "exception_pages": []}))
    review = write("review.json", p5_canonical_bytes({"schema_version": "1.0", "artifact_type": "deck_consistency_report", "deck_id": "D05", "reviewer_recommendation": "pass", "issues": [], "mandatory_checks": {"typography_consistent": True, "palette_consistent": True, "background_consistent": True, "card_language_consistent": True, "density_spacing_consistent": True, "visual_treatment_consistent": True, "navigation_consistent": True, "section_hierarchy_consistent": True, "same_deck_identity": True, "no_reopened_p4_fidelity": True}, "structured_upstream_revision": None, "evidence": {"contact_sheets_sha256": [], "exception_review_hashes": []}}))
    roundtrip = write("roundtrip.json", p5_canonical_bytes({"schema_version": "1.0", "artifact_type": "powerpoint_roundtrip_report", "deck_id": "D05", "roundtrip_copy_sha256": "a" * 64, "structural_comparison": {"slide_count_same": True, "slide_order_same": True, "slide_size_same": True}, "canonical_text_same": True, "element_counts_same": True, "chart_data_same": True, "workbook_data_same": True, "media_same": True, "relationship_safety": "safe", "external_relationships": 0, "macro_ole": 0, "slides": [], "status": "pass"}))
    decision = write("decision.json", p5_canonical_bytes({"schema_version": "1.0", "artifact_type": "deck_delivery_decision", "deck_id": "D05", "status": "pass", "policy_summary": {"critical": 0, "major": 0, "minor": 0, "review_incomplete": 0, "unexpected_reviewer_calls": 0}, "delivered_pptx_sha256": file_sha256(candidate), "references": {"qa_report_sha256": json.loads(qa.read_bytes()) and "", "roundtrip_report_sha256": "", "deck_consistency_report_sha256": "", "exception_review_hashes": []}, "p4_candidate_report_sha256": "e" * 64, "warning_approval": None, "upstream_revision": None}))
    render_manifest = write("manifest.json", p5_canonical_bytes({"schema_version": "1.0", "artifact_type": "p5_final_render_manifest", "deck_id": "D05", "renderer": "Microsoft PowerPoint", "renderer_version": "COM 16.0; file 16.0.20228.20190", "width_px": 160, "height_px": 90, "ppt_sha256": file_sha256(candidate), "slides": [], "p4_inheritance": {"p4_candidate_render_report_sha256": "f" * 64, "p4_post_assembly_report_sha256": "g" * 64, "p4_fidelity_inherited": True}, "status": "pass"}))
    asset_manifest = write("asset-manifest.json", p5_canonical_bytes({"assets": [{"path": "icon.svg"}]}))
    contact = write("approved-preview-contact-sheet.png", b"png bytes")
    render = write("final-slide-001.png", b"render png")
    asset = write("icon.svg", b"<svg/>")
    return {
        "candidate": candidate, "qa": qa, "review": review, "roundtrip": roundtrip, "decision": decision,
        "render_manifest": render_manifest, "contact": contact, "render": render, "asset": asset, "asset_manifest": asset_manifest,
    }


def _decision(fixture: dict, status: str = "pass", references: dict | None = None, warning_approval: dict | None = None) -> dict:
    from canonical_artifact import canonical_sha256
    from schema_utils import load_json as lj
    refs = references or {
        "qa_report_sha256": canonical_sha256(lj(fixture["qa"])),
        "roundtrip_report_sha256": canonical_sha256(lj(fixture["roundtrip"])),
        "deck_consistency_report_sha256": canonical_sha256(lj(fixture["review"])),
        "exception_review_hashes": [],
    }
    return {
        "schema_version": "1.0", "artifact_type": "deck_delivery_decision", "deck_id": "D05", "status": status,
        "policy_summary": {"critical": 0, "major": 0, "minor": 1 if status == "pass_with_warnings" else 0, "review_incomplete": 0, "unexpected_reviewer_calls": 0},
        "delivered_pptx_sha256": file_sha256(fixture["candidate"]),
        "references": refs, "p4_candidate_report_sha256": "e" * 64,
        "warning_approval": warning_approval, "upstream_revision": None,
    }


def _state(path: Path, state_name: str = "packaging", extra_artifacts: dict | None = None, lock_hash: str = "x" * 64) -> dict:
    artifacts = {"candidate_deck_sha256": file_sha256(path / "candidate.pptx"), "delivery_packaging_runtime_lock_sha256": lock_hash}
    if extra_artifacts:
        artifacts.update(extra_artifacts)
    return {
        "schema_version": "1.0", "artifact_type": "deck_delivery_state", "deck_id": "D05", "state": state_name,
        "budgets": {"exception_batch_size": 4, "exception_batch_calls": 2, "reviewer_technical_retries": 2, "deck_consistency_passes": 1},
        "counters": {"exception_reviewer_calls": 0, "deck_reviewer_calls": 1, "unexpected_reviewer_calls": 0},
        "current_artifacts": artifacts, "warning_acceptance": None, "history": [],
    }


class P5PackagingTests(unittest.TestCase):
    def test_candidate_package_forbids_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            fixture = _fixture(base)
            lock = lock_packaging_runtime()
            result = build_package_candidate(deck_id="D05", output_name="deck", candidate_pptx=fixture["candidate"], work_root=base, lock_document=lock, previews={"approved-preview-contact-sheet.png": fixture["contact"], "manifest.json": fixture["render_manifest"]}, assets=[("assets/icon.svg", fixture["asset"])], asset_manifest=fixture["asset_manifest"], preview_manifest=fixture["render_manifest"], qa_report=fixture["qa"], roundtrip_report=fixture["roundtrip"], authority_hashes={})
            self.assertTrue(result["delivery_forbidden"])
            self.assertFalse(result["formal_delivery_created"])
            self.assertEqual(result["package_candidate_hash_closure"], "pass")
            candidate_dir = Path(result["candidate_dir"])
            names = {path.name for path in candidate_dir.iterdir() if path.is_file()}
            self.assertEqual(len(names), 6)
            # no decision / no deck consistency report inside the candidate
            self.assertFalse(any("decision" in name for name in names))
            self.assertFalse(any("consistency" in name for name in names))
            manifest = load_json(candidate_dir / "deck_package-candidate-manifest.json")
            self.assertEqual(manifest["artifact_type"], "delivery_package_candidate")
            self.assertEqual(manifest["delivery_forbidden"], True)
            self.assertEqual(manifest["live_review_status"], "pending")
            self.assertIsNone(manifest["formal_decision_sha256"])
            # previews.zip and assets.zip must contain their manifests
            with zipfile.ZipFile(candidate_dir / "deck_previews.zip") as archive:
                self.assertIn("preview-manifest.json", archive.namelist())
            with zipfile.ZipFile(candidate_dir / "deck_assets.zip") as archive:
                self.assertIn("asset-manifest.json", archive.namelist())

    def test_candidate_package_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            fixture = _fixture(base)
            lock = lock_packaging_runtime()
            first = build_package_candidate(deck_id="D05", output_name="deck", candidate_pptx=fixture["candidate"], work_root=base / "w1", lock_document=lock, previews={"manifest.json": fixture["render_manifest"]}, assets=[("assets/icon.svg", fixture["asset"])], asset_manifest=fixture["asset_manifest"], preview_manifest=fixture["render_manifest"], qa_report=fixture["qa"], roundtrip_report=fixture["roundtrip"], authority_hashes={})
            second = build_package_candidate(deck_id="D05", output_name="deck", candidate_pptx=fixture["candidate"], work_root=base / "w2", lock_document=lock, previews={"manifest.json": fixture["render_manifest"]}, assets=[("assets/icon.svg", fixture["asset"])], asset_manifest=fixture["asset_manifest"], preview_manifest=fixture["render_manifest"], qa_report=fixture["qa"], roundtrip_report=fixture["roundtrip"], authority_hashes={})
            self.assertEqual(first["files"], second["files"])
            self.assertTrue(first["idempotent"] is False)
            self.assertTrue(second["idempotent"] is False)

    def test_formal_packaging_wrong_state_rejected_no_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            fixture = _fixture(base)
            lock = lock_packaging_runtime()
            from canonical_artifact import canonical_sha256 as _canon
            state = _state(base, state_name="live_review_pending", lock_hash=_canon(lock))
            decision_path = base / "decision.json"
            decision_path.write_bytes(p5_canonical_bytes(_decision(fixture)))
            with self.assertRaises(ContractError):
                package_formal_delivery(deck_id="D05", output_name="deck", candidate_pptx=fixture["candidate"], dist_root=base / "dist", lock_document=lock, previews={}, assets=[], asset_manifest=fixture["asset_manifest"], preview_manifest=fixture["render_manifest"], qa_report=fixture["qa"], deck_consistency_report=fixture["review"], roundtrip_report=fixture["roundtrip"], decision=decision_path, state=state, p4_candidate_sha=file_sha256(fixture["candidate"]), authority_hashes={}, reviewer_summary={})
            self.assertFalse((base / "dist").exists())

    def test_formal_packaging_stale_reference_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            fixture = _fixture(base)
            lock = lock_packaging_runtime()
            from canonical_artifact import canonical_sha256 as _canon
            state = _state(base, state_name="packaging", lock_hash=_canon(lock))
            # stale QA reference
            stale_refs = {"qa_report_sha256": "0" * 64, "roundtrip_report_sha256": "1" * 64, "deck_consistency_report_sha256": "2" * 64, "exception_review_hashes": []}
            decision_path = base / "decision.json"
            decision_path.write_bytes(p5_canonical_bytes(_decision(fixture, references=stale_refs)))
            with self.assertRaises(ContractError):
                package_formal_delivery(deck_id="D05", output_name="deck", candidate_pptx=fixture["candidate"], dist_root=base / "dist", lock_document=lock, previews={}, assets=[], asset_manifest=fixture["asset_manifest"], preview_manifest=fixture["render_manifest"], qa_report=fixture["qa"], deck_consistency_report=fixture["review"], roundtrip_report=fixture["roundtrip"], decision=decision_path, state=state, p4_candidate_sha=file_sha256(fixture["candidate"]), authority_hashes={}, reviewer_summary={})
            self.assertFalse((base / "dist").exists())

    def test_formal_packaging_warnings_without_acceptance_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            fixture = _fixture(base)
            lock = lock_packaging_runtime()
            from canonical_artifact import canonical_sha256 as _canon
            state = _state(base, state_name="packaging", lock_hash=_canon(lock))
            decision_path = base / "decision.json"
            decision_path.write_bytes(p5_canonical_bytes(_decision(fixture, status="pass_with_warnings", warning_approval=None)))
            with self.assertRaises(ContractError):
                package_formal_delivery(deck_id="D05", output_name="deck", candidate_pptx=fixture["candidate"], dist_root=base / "dist", lock_document=lock, previews={}, assets=[], asset_manifest=fixture["asset_manifest"], preview_manifest=fixture["render_manifest"], qa_report=fixture["qa"], deck_consistency_report=fixture["review"], roundtrip_report=fixture["roundtrip"], decision=decision_path, state=state, p4_candidate_sha=file_sha256(fixture["candidate"]), authority_hashes={}, reviewer_summary={})
            self.assertFalse((base / "dist").exists())

    def test_formal_packaging_success_and_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            fixture = _fixture(base)
            lock = lock_packaging_runtime()
            from canonical_artifact import canonical_sha256 as _canon
            state = _state(base, state_name="packaging", lock_hash=_canon(lock))
            decision_path = base / "decision.json"
            decision_path.write_bytes(p5_canonical_bytes(_decision(fixture)))
            authority_hashes = {
                "p4_state_sha256": "a" * 64, "p4_manifest_sha256": "b" * 64, "p4_candidate_report_sha256": "c" * 64,
                "p4_drift_report_sha256": "d" * 64, "p4_render_report_sha256": "e" * 64,
                "p5_final_render_manifest_sha256": "f" * 64, "powerpoint_roundtrip_report_sha256": "1" * 64,
                "deck_consistency_report_sha256": "2" * 64, "deck_delivery_decision_sha256": "3" * 64,
            }
            result = package_formal_delivery(deck_id="D05", output_name="deck", candidate_pptx=fixture["candidate"], dist_root=base / "dist", lock_document=lock, previews={"manifest.json": fixture["render_manifest"]}, assets=[("assets/icon.svg", fixture["asset"])], asset_manifest=fixture["asset_manifest"], preview_manifest=fixture["render_manifest"], qa_report=fixture["qa"], deck_consistency_report=fixture["review"], roundtrip_report=fixture["roundtrip"], decision=decision_path, state=state, p4_candidate_sha=file_sha256(fixture["candidate"]), authority_hashes=authority_hashes, reviewer_summary={"deck_reviewer_calls": 1})
            self.assertTrue(result["formal_delivery_created"])
            target = Path(result["dist"])
            self.assertEqual(len([path for path in target.iterdir() if path.is_file()]), 7)
            verification = verify_delivery(target=target, provenance_expected_sha256=result["provenance_sha256"], dist_root=base / "dist")
            self.assertEqual(verification["delivery_artifact_hash_closure"], "pass")

    def test_write_once_artifact_preserves_old_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            target = base / "artifact.json"
            first = {"schema_version": "1.0", "artifact_type": "warning_acceptance", "deck_id": "D05", "decision": "accept", "qa_report_sha256": "a" * 64, "deck_consistency_report_sha256": "b" * 64, "policy_sha256": "c" * 64, "user_message_sha256": "d" * 64, "accepted_at_utc": "2026-08-18T00:00:00Z", "reason_code": "warning_accepted"}
            write_once_p5_artifact(target, first)
            before = target.read_bytes()
            tampered = dict(first)
            tampered["decision"] = "reject"
            with self.assertRaises(ContractError):
                write_once_p5_artifact(target, tampered)
            self.assertEqual(target.read_bytes(), before)
            # identical bytes -> idempotent
            write_once_p5_artifact(target, first)


if __name__ == "__main__":
    unittest.main()
