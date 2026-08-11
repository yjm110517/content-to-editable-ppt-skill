from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

from environment_common import MIN_NODE, MIN_PYTHON, command_ok, command_version, normalized_executable, numeric_version, powerpoint_smoke_test, resolve_executable, runtime_error, utc_now, validate_manifest_shape, write_json


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate the Windows + PowerPoint runtime before any Agent call")
    result.add_argument("--python", type=Path)
    result.add_argument("--node", type=Path)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--skip-powerpoint-smoke", action="store_true")
    result.add_argument("--schema-dir", type=Path, default=Path(__file__).resolve().parents[1] / "schemas")
    result.add_argument("--runtime-dir", type=Path, default=Path(__file__).resolve().parent)
    return result


def inspect_runtime(args: argparse.Namespace) -> dict:
    system = platform.system()
    python_path = resolve_executable(args.python, "python") or Path(sys.executable).resolve()
    node_path = resolve_executable(args.node, "node")
    python_version = command_version(python_path, ["--version"])
    node_version = command_version(node_path, ["--version"])
    failure = None
    if system != "Windows":
        failure = runtime_error("unsupported_os", "P0.5 requires Windows", recoverable=False)
    elif numeric_version(python_version) < MIN_PYTHON:
        failure = runtime_error("python_runtime_missing", "Python 3.10 or newer is required", recoverable=True)
    elif numeric_version(node_version) < MIN_NODE:
        failure = runtime_error("node_runtime_missing", "Node 20 or newer is required", recoverable=True)
    elif not command_ok(python_path, ["-c", "import PIL,pptx,jsonschema,defusedxml,yaml,win32com.client"]):
        failure = runtime_error("python_dependency_missing", "one or more locked Python dependencies are missing", recoverable=True)
    elif not command_ok(node_path, ["--input-type=module", "-e", "await import('pptxgenjs'); await import('jszip')"], cwd=args.runtime_dir):
        failure = runtime_error("node_dependency_missing", "one or more locked Node dependencies are missing", recoverable=True)

    powerpoint = {"installed": False, "com_available": False, "smoke_test": "not_run", "version": None}
    if failure is None:
        observed = powerpoint_smoke_test(enabled=not args.skip_powerpoint_smoke)
        powerpoint = {key: observed[key] for key in ("installed", "com_available", "smoke_test", "version")}
        if not powerpoint["installed"]:
            failure = runtime_error("powerpoint_not_installed", "Microsoft PowerPoint is required", recoverable=False)
        elif not powerpoint["com_available"]:
            failure = runtime_error("powerpoint_com_unavailable", "PowerPoint COM is unavailable", recoverable=False)
        elif powerpoint["smoke_test"] == "failed":
            failure = runtime_error("powerpoint_smoke_test_failed", "PowerPoint COM smoke test failed", recoverable=False)

    ready = failure is None and (args.skip_powerpoint_smoke or powerpoint["smoke_test"] == "passed")
    manifest = {
        "schema_version": "1.0",
        "runtime_status": "ready" if ready else "environment_failure",
        "platform": {"system": system, "release": platform.release(), "machine": platform.machine(), "supported": system == "Windows"},
        "python": {"available": bool(python_version), "version": python_version, "executable": normalized_executable(python_path)},
        "node": {"available": bool(node_version), "version": node_version, "executable": normalized_executable(node_path)},
        "powerpoint": powerpoint,
        "capabilities": {"build": ready, "render": ready, "qa": ready},
        "failure": failure,
        "checked_at_utc": utc_now(),
    }
    validate_manifest_shape(manifest)
    return manifest


def main() -> int:
    args = parser().parse_args()
    manifest = inspect_runtime(args)
    write_json(args.manifest.resolve(), manifest)
    print(json.dumps({"status": manifest["runtime_status"], "manifest": str(args.manifest.resolve())}, ensure_ascii=False))
    return 0 if manifest["runtime_status"] == "ready" else 5


if __name__ == "__main__":
    raise SystemExit(main())
