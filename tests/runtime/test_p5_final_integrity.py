from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys_path = str(ROOT / "content-to-editable-ppt" / "scripts")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from canonical_artifact import canonical_sha256  # noqa: E402
from delivery_authority import file_sha256 as _file_sha256, load_delivery_authority  # noqa: E402
from final_integrity import decoded_rgb_sha256, verify_final_integrity  # noqa: E402
from schema_utils import ContractError  # noqa: E402
from PIL import Image  # noqa: E402


def _png(path: Path, color: tuple[int, int, int] = (10, 20, 30), size: tuple[int, int] = (160, 90)) -> Path:
    with Image.new("RGB", size, color) as image:
        image.save(path, format="PNG", compress_level=9)
    return path


def _p4_authority(decks: list[dict], candidate_sha: str = "", manifest_path: Path | None = None) -> dict:
    """P4 artifacts for one deck. When manifest_path is given, the fixture writes the manifest
    there and binds the P4 state to its CANONICAL hash and the candidate report to its FILE hash
    (the legacy P4 contract verified by the P5 Compatibility View)."""
    state = {
        "schema_version": "1.0", "artifact_type": "reconstruction_deck_state", "deck_id": "D05",
        "state": "p4_complete",
        "budgets": {"smoke_page_limit": 2, "targeted_patch_per_page": 2, "technical_retry_per_stage": 2, "reviewer_per_exception": 1},
        "counters": {"initial_planner_calls": 0, "targeted_patch_planner_calls": 0, "reviewer_calls": 0, "image_generation_calls": 0},
        "page_states": [], "current_artifacts": {"candidate_deck_sha256": candidate_sha or "0" * 64, "reconstruction_manifest_sha256": "1" * 64}, "history": [],
    }
    slides = [
        {"slide_id": item["slide_id"], "order": item["order"], "spec_path": f"pages/{item['slide_id']}/visual-reconstruction-spec.json", "spec_sha256": "a" * 64, "page_pptx_path": f"pages/{item['slide_id']}/page.pptx", "page_pptx_sha256": "b" * 64, "page_render_path": f"pages/{item['slide_id']}/render/slide-001.png", "page_render_sha256": "c" * 64, "order_sensitive": False, "reused": False}
        for item in decks
    ]
    manifest = {"schema_version": "1.0", "artifact_type": "reconstruction_manifest", "deck_id": "D05", "approved_design_preview_manifest_sha256": "e" * 64, "asset_manifest_sha256": "f" * 64, "slides": slides, "status": "pages_reconstructed"}
    manifest_file_sha = "1" * 64
    manifest_canonical = "1" * 64
    if manifest_path is not None:
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        manifest_file_sha = _file_sha256(manifest_path)
        manifest_canonical = canonical_sha256(json.loads(manifest_path.read_text(encoding="utf-8")))
        state["current_artifacts"]["reconstruction_manifest_sha256"] = manifest_canonical
    render_slides = [{"order": item["order"], "path": f"slide-{item['order']:03d}.png", "sha256": "d" * 64} for item in decks]
    return {
        "state": state,
        "manifest": manifest,
        "manifest_file_sha256": manifest_file_sha,
        "manifest_canonical_sha256": manifest_canonical,
        "candidate_report": {"schema_version": "1.0", "artifact_type": "candidate_deck_report", "deck_id": "D05", "candidate_pptx_path": "reconstruction-candidate.pptx", "candidate_pptx_sha256": candidate_sha or "0" * 64, "reconstruction_manifest_sha256": manifest_file_sha, "slide_count": len(decks), "slide_order": [item["slide_id"] for item in decks], "delivery_forbidden": True, "status": "built"},
        "drift_report": {"schema_version": "1.0", "artifact_type": "post_assembly_drift_report", "deck_id": "D05", "candidate_deck_sha256": candidate_sha or "0" * 64, "slides": [{"slide_id": item["slide_id"], "order": item["order"], "page_render_sha256": "9" * 64, "assembled_render_sha256": "9" * 64, "pixel_identical": True, "drift_code": None} for item in decks], "post_assembly_slide_drift": 0, "unexpected_assembly_mutation": 0, "status": "pass"},
        "render_report": {"schema_version": "1.0", "artifact_type": "reconstruction_render_report", "renderer": "Microsoft PowerPoint", "renderer_version": "COM 16.0; file 16.0.20228.20190", "width_px": 160, "height_px": 90, "ppt_sha256": candidate_sha or "0" * 64, "rendered_page_count": len(decks), "slides": render_slides, "status": "pass"},
    }


def _write_bundle(root: Path, authority: dict) -> dict:
    state_path = root / "p4-state.json"
    manifest_path = root / "p4-manifest.json"
    candidate_path = root / "candidate-report.json"
    drift_path = root / "drift-report.json"
    render_path = root / "render-report.json"
    state_path.write_text(json.dumps(authority["state"], sort_keys=True, separators=(",", ":")), encoding="utf-8")
    manifest_path.write_text(json.dumps(authority["manifest"], sort_keys=True, separators=(",", ":")), encoding="utf-8")
    candidate_path.write_text(json.dumps(authority["candidate_report"], sort_keys=True, separators=(",", ":")), encoding="utf-8")
    drift_path.write_text(json.dumps(authority["drift_report"], sort_keys=True, separators=(",", ":")), encoding="utf-8")
    render_path.write_text(json.dumps(authority["render_report"], sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return {"state": state_path, "manifest": manifest_path, "candidate": candidate_path, "drift": drift_path, "render": render_path}


class P5FinalIntegrityTests(unittest.TestCase):
    def test_decoded_rgb_hash_is_pixel_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            a = _png(root / "a.png", (10, 20, 30))
            b = _png(root / "b.png", (10, 20, 31))
            c = _png(root / "c.png", (10, 20, 30))
            self.assertEqual(decoded_rgb_sha256(a), decoded_rgb_sha256(c))
            self.assertNotEqual(decoded_rgb_sha256(a), decoded_rgb_sha256(b))

    def test_compatibility_view_closes_legacy_manifest_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pptx = root / "candidate.pptx"
            pptx.write_bytes(b"fake pptx bytes")
            candidate_sha = _file_sha256(pptx)
            authority = _p4_authority([{"order": 1, "slide_id": "S01"}], candidate_sha=candidate_sha, manifest_path=root / "manifest-fixture.json")
            paths = _write_bundle(root, authority)
            bundle = load_delivery_authority(p4_state_path=paths["state"], p4_manifest_path=paths["manifest"], p4_candidate_report_path=paths["candidate"], p4_drift_report_path=paths["drift"], p4_render_report_path=paths["render"], p4_candidate_pptx=pptx)
            view = bundle["manifest_compatibility"]
            self.assertEqual(view["status"], "closed")
            # legacy candidate field is the manifest FILE hash; state field is the CANONICAL hash
            self.assertEqual(view["legacy_candidate_manifest_file_sha256"], authority["manifest_file_sha256"])
            self.assertEqual(view["state_manifest_canonical_sha256"], authority["manifest_canonical_sha256"])
            self.assertEqual(view["manifest_file_sha256"], _file_sha256(paths["manifest"]))
            self.assertEqual(view["manifest_canonical_sha256"], canonical_sha256(authority["manifest"]))

    def test_manifest_file_hash_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pptx = root / "candidate.pptx"
            pptx.write_bytes(b"fake pptx bytes")
            candidate_sha = _file_sha256(pptx)
            authority = _p4_authority([{"order": 1, "slide_id": "S01"}], candidate_sha=candidate_sha)
            authority["candidate_report"]["reconstruction_manifest_sha256"] = "2" * 64  # wrong file hash
            paths = _write_bundle(root, authority)
            with self.assertRaises(ContractError) as context:
                load_delivery_authority(p4_state_path=paths["state"], p4_manifest_path=paths["manifest"], p4_candidate_report_path=paths["candidate"], p4_drift_report_path=paths["drift"], p4_render_report_path=paths["render"], p4_candidate_pptx=pptx)
            codes = [item["code"] for item in context.exception.errors]
            self.assertIn("authority_hash_mismatch", codes)

    def test_manifest_canonical_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pptx = root / "candidate.pptx"
            pptx.write_bytes(b"fake pptx bytes")
            candidate_sha = _file_sha256(pptx)
            authority = _p4_authority([{"order": 1, "slide_id": "S01"}], candidate_sha=candidate_sha)
            authority["state"]["current_artifacts"]["reconstruction_manifest_sha256"] = "3" * 64  # wrong canonical
            paths = _write_bundle(root, authority)
            with self.assertRaises(ContractError) as context:
                load_delivery_authority(p4_state_path=paths["state"], p4_manifest_path=paths["manifest"], p4_candidate_report_path=paths["candidate"], p4_drift_report_path=paths["drift"], p4_render_report_path=paths["render"], p4_candidate_pptx=pptx)
            codes = [item["code"] for item in context.exception.errors]
            self.assertIn("authority_hash_mismatch", codes)

    def test_candidate_hash_mismatch_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pptx = root / "candidate.pptx"
            pptx.write_bytes(b"fake pptx bytes")
            # manifest file/canonical hashes are bound correctly; the candidate file hash is wrong
            authority = _p4_authority([{"order": 1, "slide_id": "S01"}], candidate_sha="0" * 64, manifest_path=root / "manifest-fixture.json")
            paths = _write_bundle(root, authority)
            with self.assertRaises(ContractError) as context:
                load_delivery_authority(p4_state_path=paths["state"], p4_manifest_path=paths["manifest"], p4_candidate_report_path=paths["candidate"], p4_drift_report_path=paths["drift"], p4_render_report_path=paths["render"], p4_candidate_pptx=pptx)
            codes = [item["code"] for item in context.exception.errors]
            self.assertIn("authority_hash_mismatch", codes)

    def test_integrity_verification_with_mocked_render(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pptx = root / "candidate.pptx"
            pptx.write_bytes(b"fake pptx bytes")
            candidate_sha = hashlib.sha256(b"fake pptx bytes").hexdigest()
            render_dir = root / "p4-renders"
            render_dir.mkdir()
            png = _png(render_dir / "slide-001.png", (10, 20, 30))
            authority = _p4_authority([{"order": 1, "slide_id": "S01"}], candidate_sha=candidate_sha)
            authority["state"]["current_artifacts"]["candidate_deck_sha256"] = candidate_sha
            authority["candidate_report"]["candidate_pptx_sha256"] = candidate_sha
            authority["drift_report"]["candidate_deck_sha256"] = candidate_sha
            authority["render_report"]["ppt_sha256"] = candidate_sha
            bundle = {
                "deck_id": "D05",
                "p4_candidate_pptx_sha256": candidate_sha,
                "p4_drift_report": authority["drift_report"],
                "p4_render_report": authority["render_report"],
                "p4_candidate_report": authority["candidate_report"],
            }
            p5_render_dir = root / "p5-renders"
            p5_render_dir.mkdir()
            shutil.copy2(png, p5_render_dir / "slide-001.png")
            p5_render_report = root / "p5-render-report.json"
            fake_render = {
                "renderer": "Microsoft PowerPoint",
                "renderer_version": "COM 16.0; file 16.0.20228.20190",
                "width_px": 160, "height_px": 90,
                "slides": [{"order": 1, "path": "slide-001.png", "sha256": hashlib.sha256(png.read_bytes()).hexdigest()}],
            }
            with mock.patch("final_integrity.render_candidate_pptx", return_value=fake_render) as mocked:
                manifest = verify_final_integrity(
                    bundle=bundle, candidate_pptx=pptx, p4_render_root=render_dir,
                    p5_render_dir=p5_render_dir, p5_render_report_path=p5_render_report,
                    width_px=160, height_px=90,
                )
            mocked.assert_called_once()
            self.assertEqual(manifest["status"], "pass")
            self.assertTrue(manifest["p4_inheritance"]["p4_fidelity_inherited"])
            self.assertEqual(manifest["slides"][0]["decoded_rgb_sha256"], decoded_rgb_sha256(png))

    def test_renderer_version_drift_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pptx = root / "candidate.pptx"
            pptx.write_bytes(b"fake pptx bytes")
            candidate_sha = hashlib.sha256(b"fake pptx bytes").hexdigest()
            render_dir = root / "p4-renders"
            render_dir.mkdir()
            _png(render_dir / "slide-001.png", (10, 20, 30))
            authority = _p4_authority([{"order": 1, "slide_id": "S01"}], candidate_sha=candidate_sha)
            authority["render_report"]["ppt_sha256"] = candidate_sha
            bundle = {
                "deck_id": "D05",
                "p4_candidate_pptx_sha256": candidate_sha,
                "p4_drift_report": authority["drift_report"],
                "p4_render_report": authority["render_report"],
                "p4_candidate_report": authority["candidate_report"],
            }
            fake_render = dict(authority["render_report"])
            fake_render["renderer_version"] = "COM 16.0; file 16.0.99999.99999"
            with mock.patch("final_integrity.render_candidate_pptx", return_value=fake_render):
                with self.assertRaises(ContractError) as context:
                    verify_final_integrity(
                        bundle=bundle, candidate_pptx=pptx, p4_render_root=render_dir,
                        p5_render_dir=root / "p5-renders", p5_render_report_path=root / "p5-render-report.json",
                        width_px=160, height_px=90,
                    )
            self.assertEqual(context.exception.errors[0]["code"], "render_runtime_mismatch")


if __name__ == "__main__":
    unittest.main()
