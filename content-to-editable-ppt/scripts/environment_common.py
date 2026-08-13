from __future__ import annotations

import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


MIN_PYTHON = (3, 10)
MIN_NODE = (20, 0)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def normalized_executable(path: Path | None) -> str | None:
    if path is None:
        return None
    return "${NORMALIZED_RUNTIME_PATH}/" + path.name


def resolve_executable(explicit: Path | None, name: str) -> Path | None:
    if explicit is not None:
        candidate = explicit.resolve()
        return candidate if candidate.is_file() else None
    resolved = shutil.which(name)
    return Path(resolved).resolve() if resolved else None


def command_version(executable: Path | None, arguments: list[str]) -> str | None:
    if executable is None:
        return None
    try:
        result = subprocess.run([str(executable), *arguments], capture_output=True, text=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return (result.stdout or result.stderr).strip().splitlines()[0]


def command_ok(executable: Path | None, arguments: list[str], *, cwd: Path | None = None) -> bool:
    if executable is None:
        return False
    try:
        subprocess.run([str(executable), *arguments], cwd=cwd, capture_output=True, text=True, timeout=30, check=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def numeric_version(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    match = re.search(r"(\d+)(?:\.(\d+))?", value)
    return tuple(int(part) for part in match.groups(default="0")) if match else ()


def runtime_error(code: str, message: str, *, recoverable: bool, stage: str = "preflight") -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "code": code,
        "category": "environment_failure",
        "stage": stage,
        "recoverable": recoverable,
        "issue_scope": "environment",
        "artifact_path": None,
        "normalized_message": message,
        "attempt": 0,
    }


def powerpoint_smoke_test(enabled: bool = True) -> dict[str, Any]:
    if platform.system() != "Windows":
        return {"installed": False, "com_available": False, "smoke_test": "not_run", "version": None, "error": "unsupported_os"}
    try:
        import win32com.client  # type: ignore
    except ImportError:
        return {"installed": False, "com_available": False, "smoke_test": "not_run", "version": None, "error": "pywin32_missing"}
    app = None
    presentation = None
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        app.Visible = True
        version = str(app.Version)
        if not enabled:
            return {"installed": True, "com_available": True, "smoke_test": "not_run", "version": version, "error": None}
        with tempfile.TemporaryDirectory(prefix="content-ppt-preflight-") as temp:
            root = Path(temp)
            pptx = root / "smoke.pptx"
            render_dir = root / "render"
            presentation = app.Presentations.Add()
            slide = presentation.Slides.Add(1, 12)
            shape = slide.Shapes.AddTextbox(1, 24, 24, 360, 48)
            shape.TextFrame.TextRange.Text = "Content to Editable PPT runtime smoke"
            presentation.SaveAs(str(pptx), 24)
            presentation.Export(str(render_dir), "PNG", 320, 180)
            presentation.Close()
            presentation = None
            if not pptx.is_file() or not list(render_dir.glob("*.PNG")):
                raise RuntimeError("PowerPoint did not create the expected smoke artifacts")
        return {"installed": True, "com_available": True, "smoke_test": "passed", "version": version, "error": None}
    except Exception as exc:
        message = re.sub(r"[A-Za-z]:\\[^\s\"']+", "${NORMALIZED_RUNTIME_PATH}", str(exc))
        return {"installed": app is not None, "com_available": app is not None, "smoke_test": "failed", "version": None, "error": message or "powerpoint_smoke_test_failed"}
    finally:
        if presentation is not None:
            try:
                presentation.Close()
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass


def write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def validate_manifest_shape(manifest: dict[str, Any]) -> None:
    required = {"schema_version", "runtime_status", "platform", "python", "node", "powerpoint", "capabilities", "failure", "checked_at_utc"}
    if manifest.get("schema_version") == "1.1":
        required.add("tools")
    if set(manifest) != required:
        raise ValueError("runtime manifest fields do not match the 1.0 contract")
    if manifest["schema_version"] not in {"1.0", "1.1"} or manifest["runtime_status"] not in {"ready", "environment_failure"}:
        raise ValueError("runtime manifest status is invalid")
    if manifest["schema_version"] == "1.1":
        rasterizer = manifest["tools"].get("svg_rasterizer", {})
        if rasterizer.get("package") != "@resvg/resvg-js" or rasterizer.get("version") not in {"2.6.2", None}:
            raise ValueError("runtime manifest SVG rasterizer is invalid")
    for name in ("python", "node"):
        executable = manifest[name]["executable"]
        if executable is not None and not executable.startswith("${NORMALIZED_RUNTIME_PATH}/"):
            raise ValueError("runtime manifest leaked a non-normalized executable path")
