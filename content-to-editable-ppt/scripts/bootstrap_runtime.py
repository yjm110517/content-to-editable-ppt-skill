from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Bootstrap the managed P0.5 runtime without changing system software")
    result.add_argument("--python", type=Path, default=Path(sys.executable))
    result.add_argument("--node", type=Path)
    result.add_argument("--manifest", type=Path, required=True)
    result.add_argument("--install-dependencies", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    scripts = Path(__file__).resolve().parent
    if args.install_dependencies:
        subprocess.run([str(args.python), "-m", "pip", "install", "-r", str(scripts / "requirements.txt")], check=True)
    command = [str(args.python), str(scripts / "environment_preflight.py"), "--python", str(args.python), "--manifest", str(args.manifest)]
    if args.node:
        command.extend(["--node", str(args.node)])
    return subprocess.run(command).returncode


if __name__ == "__main__":
    raise SystemExit(main())
