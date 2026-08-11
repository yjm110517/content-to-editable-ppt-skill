from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "content-to-editable-ppt" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import environment_preflight


class EnvironmentPreflightTests(unittest.TestCase):
    def _args(self, manifest: Path) -> argparse.Namespace:
        return argparse.Namespace(
            python=Path(sys.executable),
            node=None,
            manifest=manifest,
            skip_powerpoint_smoke=False,
            schema_dir=ROOT / "content-to-editable-ppt" / "schemas",
            runtime_dir=SCRIPTS,
        )

    @patch("environment_preflight.platform.system", return_value="Windows")
    @patch("environment_preflight.powerpoint_smoke_test")
    @patch("environment_preflight.command_ok", return_value=True)
    @patch("environment_preflight.resolve_executable")
    @patch("environment_preflight.command_version")
    def test_ready_requires_all_capabilities(self, version, resolve, command_ok, smoke, system) -> None:
        version.side_effect = ["Python 3.12.13", "v24.14.0"]
        resolve.side_effect = [Path(sys.executable), Path("C:/runtime/node.exe")]
        smoke.return_value = {"installed": True, "com_available": True, "smoke_test": "passed", "version": "16.0", "error": None}
        with tempfile.TemporaryDirectory() as temp:
            manifest = environment_preflight.inspect_runtime(self._args(Path(temp) / "runtime-manifest.json"))
        self.assertEqual(manifest["runtime_status"], "ready")
        self.assertEqual(manifest["python"]["executable"], "${NORMALIZED_RUNTIME_PATH}/python.exe")

    @patch("environment_preflight.platform.system", return_value="Linux")
    def test_unsupported_os_is_non_repairable(self, system) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest = environment_preflight.inspect_runtime(self._args(Path(temp) / "runtime-manifest.json"))
        self.assertEqual(manifest["runtime_status"], "environment_failure")
        self.assertEqual(manifest["failure"]["code"], "unsupported_os")
        self.assertFalse(manifest["failure"]["recoverable"])

    @patch("environment_preflight.platform.system", return_value="Windows")
    @patch("environment_preflight.command_ok", return_value=False)
    @patch("environment_preflight.resolve_executable")
    @patch("environment_preflight.command_version")
    def test_missing_python_dependency_is_repairable(self, version, resolve, command_ok, system) -> None:
        version.side_effect = ["Python 3.12.13", "v24.14.0"]
        resolve.side_effect = [Path(sys.executable), Path("C:/runtime/node.exe")]
        with tempfile.TemporaryDirectory() as temp:
            manifest = environment_preflight.inspect_runtime(self._args(Path(temp) / "runtime-manifest.json"))
        self.assertEqual(manifest["failure"]["code"], "python_dependency_missing")
        self.assertTrue(manifest["failure"]["recoverable"])


if __name__ == "__main__":
    unittest.main()
