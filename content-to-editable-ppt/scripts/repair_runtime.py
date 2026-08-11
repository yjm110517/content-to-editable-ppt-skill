from __future__ import annotations

import argparse
import json
import subprocess
import shutil
import sys
from pathlib import Path

from environment_common import write_json


REPAIRABLE = {"python_runtime_missing", "python_dependency_missing", "node_runtime_missing", "node_dependency_missing", "runtime_cache_missing", "runtime_manifest_stale", "runtime_path_changed"}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Perform one bounded managed-runtime repair cycle")
    result.add_argument("--failure", type=Path, required=True)
    result.add_argument("--result", type=Path, required=True)
    result.add_argument("--python", type=Path, default=Path(sys.executable))
    result.add_argument("--node", type=Path)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--pnpm", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    failure = json.loads(args.failure.read_text(encoding="utf-8"))
    code = failure.get("code")
    if code not in REPAIRABLE:
        write_json(args.result, {"status": "environment_failure", "repair_cycles": 0, "code": code, "message": "failure is not automatically repairable"})
        return 5
    scripts = Path(__file__).resolve().parent
    try:
        if code == "python_dependency_missing":
            subprocess.run([str(args.python), "-m", "pip", "install", "-r", str(scripts / "requirements.txt")], check=True)
        elif code == "node_dependency_missing":
            pnpm = args.pnpm or (Path(shutil.which("pnpm")) if shutil.which("pnpm") else None)
            if pnpm is None:
                raise RuntimeError("pnpm is required to repair Node dependencies")
            subprocess.run([str(pnpm), "install", "--frozen-lockfile"], cwd=scripts, check=True)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        write_json(args.result, {"status": "environment_failure", "repair_cycles": 1, "code": code, "message": str(exc)})
        return 5
    command = [str(args.python), str(scripts / "environment_preflight.py"), "--python", str(args.python), "--manifest", str(args.manifest)]
    if args.node:
        command.extend(["--node", str(args.node)])
    completed = subprocess.run(command)
    write_json(args.result, {"status": "ready" if completed.returncode == 0 else "environment_failure", "repair_cycles": 1, "code": code})
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
