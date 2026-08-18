from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from canonical_artifact import canonical_sha256
from style_anchor_workflow import consume, prepare
from tests.runtime.test_p3_design_preview_contracts import H, package


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class StyleAnchorWorkflowTests(unittest.TestCase):
    def test_prepare_and_consume_generation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prompt_package = package()
            package_path = root / "package.json"
            write(package_path, prompt_package)
            anchor = {
                "schema_version": "1.0", "artifact_type": "style_anchor_request", "deck_id": "D01",
                "deck_prompt_package_sha256": canonical_sha256(prompt_package),
                "deck_visual_system_sha256": prompt_package["deck_visual_system_sha256"],
                "slide_id": "S01", "slide_prompt_sha256": H,
                "selection_basis": "representativeness_first_v1", "high_risk_slide_ids": [],
                "status": "ready_for_generation",
            }
            anchor_path = root / "anchor.json"
            write(anchor_path, anchor)
            lock = {
                "schema_version": "1.0", "artifact_type": "generation_runtime_lock", "deck_id": "D01",
                "backend": "image_gen.imagegen", "provider_policy": "runtime_default", "model_policy": "runtime_default",
                "model_identity_status": "not_exposed", "model_id": None, "model_version": None,
                "runtime_fingerprint": H, "runtime_scope_id": "scope", "status": "locked",
            }
            lock_path = root / "lock.json"
            write(lock_path, lock)
            prepare(argparse.Namespace(prompt_package=package_path, anchor_request=anchor_path, runtime_lock=lock_path, output_dir=root / "call"))
            manifest = json.loads((root / "call" / "call_manifest.json").read_text())
            call = {"schema_version": "1.0", "artifact_type": "image_generation_call_record", "call_id": "call-1", **manifest, "status": "succeeded"}
            call_path = root / "call.json"
            write(call_path, call)
            raw = root / "raw.png"
            with Image.new("RGB", (1600, 900), "white") as image:
                image.save(raw)
            normalized = root / "normalized.png"
            result = consume(argparse.Namespace(call_manifest=root / "call" / "call_manifest.json", call_record=call_path, raw_layer=raw, normalized_layer=normalized, output=root / "layer.json"))
            self.assertEqual(result["generated_layer_sha256"], hashlib.sha256(normalized.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
