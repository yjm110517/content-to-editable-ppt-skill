from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Render every slide of a PPTX through Microsoft PowerPoint.")
    result.add_argument("--input", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--report", type=Path, required=True)
    result.add_argument("--width-px", type=int, required=True)
    result.add_argument("--height-px", type=int, required=True)
    result.add_argument("--timeout-seconds", type=int, default=180)
    return result


def _slide_count(path: Path) -> int:
    try:
        with zipfile.ZipFile(path) as archive:
            slides = [name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
            if not slides:
                raise ValueError("no slides")
            return len(slides)
    except (zipfile.BadZipFile, ValueError) as exc:
        raise RuntimeError("input is not a valid PPTX") from exc


def _worker(argv: list[str]) -> int:
    ppt, output_dir, width, height, state = Path(argv[0]), Path(argv[1]), int(argv[2]), int(argv[3]), Path(argv[4])
    app = presentation = None
    try:
        import pythoncom
        import win32api
        import win32com.client
        pythoncom.CoInitialize(); app = win32com.client.DispatchEx("PowerPoint.Application")
        presentation = app.Presentations.Open(str(ppt.resolve()), ReadOnly=True, Untitled=False, WithWindow=False)
        output_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, presentation.Slides.Count + 1): presentation.Slides(index).Export(str((output_dir / f"slide-{index:03d}.png").resolve()), "PNG", width, height)
        executable = Path(app.Path) / "POWERPNT.EXE"; file_version = None
        if executable.is_file():
            try:
                info = win32api.GetFileVersionInfo(str(executable), "\\"); file_version = ".".join(str(value) for value in (info["FileVersionMS"] >> 16, info["FileVersionMS"] & 0xFFFF, info["FileVersionLS"] >> 16, info["FileVersionLS"] & 0xFFFF))
            except Exception: pass
        state.write_text(json.dumps({"status":"passed","version":f"COM {app.Version}" + (f"; file {file_version}" if file_version else ""),"slide_count":presentation.Slides.Count}), encoding="utf-8"); return 0
    except Exception as exc:
        state.write_text(json.dumps({"status":"failed","message":str(exc)}), encoding="utf-8"); return 1
    finally:
        if presentation is not None:
            try: presentation.Close()
            except Exception: pass
        if app is not None:
            try: app.Quit()
            except Exception: pass
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception: pass


def _canonicalize(path: Path, width: int, height: int) -> None:
    with Image.open(path) as image:
        image.load()
        if image.size != (width, height): raise RuntimeError("PowerPoint render size mismatch")
        stream = io.BytesIO(); image.convert("RGB").save(stream, format="PNG", optimize=False, compress_level=9); path.write_bytes(stream.getvalue())


def render(args: argparse.Namespace) -> dict:
    if not args.input.is_file(): raise RuntimeError("input PPTX is missing")
    if args.output_dir.exists() or args.report.exists(): raise RuntimeError("render output already exists")
    if args.width_px < 1 or args.height_px < 1: raise RuntimeError("render dimensions must be positive")
    count = _slide_count(args.input); args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".deck-render-", dir=args.output_dir.parent) as temporary:
        stage = Path(temporary); state = stage / "state.json"; exported = stage / "slides"
        command = [sys.executable, str(Path(__file__).resolve()), "--_worker", str(args.input), str(exported), str(args.width_px), str(args.height_px), str(state)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout_seconds, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        details = json.loads(state.read_text(encoding="utf-8")) if state.exists() else {}
        if completed.returncode or details.get("status") != "passed": raise RuntimeError(details.get("message") or completed.stderr or "PowerPoint render failed")
        files = sorted(exported.glob("slide-*.png"))
        if len(files) != count: raise RuntimeError("PowerPoint render slide count mismatch")
        for item in files: _canonicalize(item, args.width_px, args.height_px)
        report = {"schema_version":"1.0","artifact_type":"deck_render_report","renderer":"Microsoft PowerPoint","renderer_version":details["version"],"ppt_sha256":sha(args.input),"width_px":args.width_px,"height_px":args.height_px,"rendered_page_count":count,"slides":[{"order":index,"path":item.name,"sha256":sha(item)} for index,item in enumerate(files,1)],"status":"pass"}
        staged_report = stage / "report.json"; staged_report.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
        shutil.copytree(exported, args.output_dir); os.replace(staged_report, args.report); return report


def main() -> int:
    args = parser().parse_args()
    try: print(json.dumps({"status":"ok","outputs":render(args)}, ensure_ascii=False)); return 0
    except Exception as exc: print(json.dumps({"status":"error","error":{"code":"powerpoint_render_failed","message":str(exc)}}, ensure_ascii=False)); return 7


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--_worker": raise SystemExit(_worker(sys.argv[2:]))
    raise SystemExit(main())
