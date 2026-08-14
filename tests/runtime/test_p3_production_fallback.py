from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
VENDOR = ROOT / "content-to-editable-ppt" / "runtime" / "vendor" / "tabler-icons" / "3.46.0"
sys.path.insert(0, str(SCRIPTS))

from build_tabler_icon_index import build_index
from canonical_artifact import canonical_sha256
from generate_icon_fallback import create_handoff, record_decision
from markdown_wireframe import bind_markdown
from resolve_icon_asset import create_record, materialize, source_for_record, verify
from schema_utils import ContractError
from search_tabler_icons import rank
from tests.runtime.test_p2_markdown_binder import MarkdownWireframeBinderTests, NOW, candidate


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ProductionFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not VENDOR.is_dir():
            raise unittest.SkipTest("managed Tabler vendor copy has not been synchronized")
        cls.index = build_index(VENDOR)

    def authority(self, root: Path) -> dict[str, Path | str]:
        helper = MarkdownWireframeBinderTests()
        bundle = helper.bundle(root)
        markdown, manifest = bind_markdown(candidate(), bundle)
        manifest["status"] = "accepted"
        wireframe_root = root / "wireframes"
        wireframe_root.mkdir()
        (wireframe_root / "deck-wireframe.md").write_bytes(markdown)
        p2_manifest = wireframe_root / "wireframe-manifest.json"
        write(p2_manifest, manifest)
        manifest_sha = canonical_sha256(manifest)
        direction = {
            "schema_version": "1.0",
            "artifact_type": "deck_visual_direction",
            "deck_id": manifest["deck_id"],
            "p2_manifest_sha256": manifest_sha,
            "icon_family": "tabler-outline",
            "created_at_utc": NOW,
        }
        direction_path = root / "visual-direction.json"
        write(direction_path, direction)
        evidence = rank(
            self.index,
            "artificial intelligence code",
            8,
            visual_ref="S01-V01",
            p2_manifest_sha256=manifest_sha,
        )
        self.assertEqual(evidence["status"], "host_selection_required")
        evidence_path = root / "search-evidence.json"
        write(evidence_path, evidence)
        return {
            "p2_manifest": p2_manifest,
            "wireframe_root": wireframe_root,
            "direction": direction_path,
            "evidence": evidence_path,
            "visual_ref": "S01-V01",
            "icon_name": evidence["top_k"][0]["name"],
        }

    def common(self, paths: dict[str, Path | str]) -> dict:
        return {
            "p2_manifest": paths["p2_manifest"],
            "wireframe_root": paths["wireframe_root"],
            "visual_direction": paths["direction"],
            "search_evidence": paths["evidence"],
            "visual_ref": paths["visual_ref"],
            "created_at_utc": NOW,
        }

    def decision(self, paths: dict[str, Path | str], root: Path, *, route: str) -> Path:
        output = root / f"{route}-decision.json"
        record_decision(argparse.Namespace(
            **self.common(paths),
            decision="select_tabler" if route == "tabler" else "raster_handoff",
            selected_icon=paths["icon_name"] if route == "tabler" else None,
            output=output,
        ))
        return output

    def test_host_top_k_decision_materializes_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.authority(root)
            decision = self.decision(paths, root, route="tabler")
            record = root / "resolution-record.json"
            create_record(argparse.Namespace(
                **self.common(paths), icon_name=paths["icon_name"], selection_method="host_from_top_k",
                selection_decision=decision, vendor_root=VENDOR, output=record,
            ))
            assets = root / "resolved" / "assets"
            materialize(argparse.Namespace(resolution_record=record, vendor_root=VENDOR, output_dir=assets))
            result = verify(argparse.Namespace(
                p2_manifest=paths["p2_manifest"], wireframe_root=paths["wireframe_root"],
                visual_direction=paths["direction"], search_evidence=paths["evidence"],
                selection_decision=decision, resolution_record=record, vendor_root=VENDOR,
                asset_manifest=assets.parent / "asset_manifest.json",
                security_report=assets.parent / "svg_security_report.json",
                consumption_contract=assets.parent / "consumption-contract.json",
            ))
            self.assertEqual(result["status"], "verified")

    def test_raster_handoff_is_bound_write_once_and_creates_no_svg_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.authority(root)
            decision = self.decision(paths, root, route="handoff")
            output = root / "raster-handoff-pending.json"
            result = create_handoff(argparse.Namespace(**self.common(paths), selection_decision=decision, output=output))
            self.assertEqual(result["status"], "raster_handoff_pending")
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(record["selection_decision_sha256"], canonical_sha256(json.loads(decision.read_text(encoding="utf-8"))))
            for name in ("asset_manifest.json", "svg_security_report.json", "consumption-contract.json"):
                self.assertFalse((root / name).exists())
            self.assertFalse(any(root.rglob("*.svg")))
            original = output.read_bytes()
            with self.assertRaises(ContractError) as raised:
                create_handoff(argparse.Namespace(**self.common(paths), selection_decision=decision, output=output))
            self.assertIn("overwrite_forbidden", {item["code"] for item in raised.exception.errors})
            self.assertEqual(output.read_bytes(), original)

    def test_missing_tampered_and_cross_deck_decisions_are_rejected_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.authority(root)
            output = root / "handoff.json"
            with self.assertRaises((ContractError, FileNotFoundError)):
                create_handoff(argparse.Namespace(**self.common(paths), selection_decision=root / "missing.json", output=output))
            self.assertFalse(output.exists())
            decision = self.decision(paths, root, route="handoff")
            changed = json.loads(decision.read_text(encoding="utf-8"))
            changed["deck_id"] = "OTHER"
            decision.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(ContractError) as raised:
                create_handoff(argparse.Namespace(**self.common(paths), selection_decision=decision, output=output))
            self.assertIn("authority_hash_mismatch", {item["code"] for item in raised.exception.errors})
            self.assertFalse(output.exists())

    def test_selection_outside_top_k_and_unknown_visual_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = self.authority(root)
            with self.assertRaises(ContractError) as raised:
                record_decision(argparse.Namespace(
                    **self.common(paths), decision="select_tabler", selected_icon="not-in-top-k", output=root / "bad.json",
                ))
            self.assertIn("selection_not_in_top_k", {item["code"] for item in raised.exception.errors})
            bad = self.common(paths)
            bad["visual_ref"] = "OTHER-V01"
            with self.assertRaises(ContractError):
                record_decision(argparse.Namespace(**bad, decision="raster_handoff", selected_icon=None, output=root / "unknown.json"))

    def test_production_rejects_legacy_records_and_external_svg(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = {
                "schema_version": "1.0", "artifact_type": "icon_resolution_record", "visual_ref": "S01-V01",
                "p2_manifest_sha256": "a" * 64, "resolution_method": "programmatic_svg",
                "source_sha256": "b" * 64, "selection_method": "bounded_fallback",
                "drawing_spec_sha256": "c" * 64, "created_at_utc": NOW,
            }
            legacy_path = root / "legacy.json"
            write(legacy_path, legacy)
            with self.assertRaises(ContractError) as raised:
                materialize(argparse.Namespace(resolution_record=legacy_path, vendor_root=VENDOR, output_dir=root / "assets"))
            self.assertIn("production_resolution_method_forbidden", {item["code"] for item in raised.exception.errors})
            with self.assertRaises(ContractError) as external:
                source_for_record({"resolution_method": "tabler_existing"}, VENDOR, root / "arbitrary.svg")
            self.assertIn("production_resolution_method_forbidden", {item["code"] for item in external.exception.errors})

    def test_public_cli_does_not_advertise_legacy_routes_or_source_svg(self) -> None:
        resolver = subprocess.run([sys.executable, str(SCRIPTS / "resolve_icon_asset.py"), "--help"], capture_output=True, text=True, check=True)
        fallback = subprocess.run([sys.executable, str(SCRIPTS / "generate_icon_fallback.py"), "--help"], capture_output=True, text=True, check=True)
        self.assertNotIn("--source-svg", resolver.stdout)
        self.assertNotIn("compose", fallback.stdout)
        self.assertNotIn("draw", fallback.stdout)
        self.assertIn("create-handoff", fallback.stdout)


if __name__ == "__main__":
    unittest.main()
