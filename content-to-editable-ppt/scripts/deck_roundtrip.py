from __future__ import annotations

import argparse
import hashlib
import io
import json
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from PIL import Image

from final_integrity import decoded_rgb_sha256, file_sha256
from schema_utils import ContractError, error, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}
OBJECT_TAGS = {f"{{{NS['p']}}}sp", f"{{{NS['p']}}}pic", f"{{{NS['p']}}}graphicFrame", f"{{{NS['p']}}}cxnSp", f"{{{NS['p']}}}grpSp"}
PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
CHART_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run PowerPoint Open/SaveAs/Reopen/Render roundtrip on a P4 candidate copy with real semantic comparison.")
    result.add_argument("--deck-id", required=True)
    result.add_argument("--candidate-pptx", type=Path, required=True)
    result.add_argument("--p4-manifest", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--width-px", type=int, required=True)
    result.add_argument("--height-px", type=int, required=True)
    result.add_argument("--timeout-seconds", type=int, default=240)
    return result


def _slide_names(archive: zipfile.ZipFile) -> list[str]:
    names = [name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
    names.sort(key=lambda name: int(name.rsplit("/", 1)[-1].split("slide")[1].split(".")[0]))
    return names


def _c_nv_pr(element: ET.Element) -> ET.Element | None:
    for prefix in ("nvSpPr", "nvPicPr", "nvGraphicFramePr", "nvCxnSpPr", "nvGrpSpPr"):
        found = element.find(f"{{{NS['p']}}}{prefix}/{{{NS['p']}}}cNvPr")
        if found is not None:
            return found
    return None


def _slide_object_names(root: ET.Element) -> list[str]:
    names: list[str] = []
    for element in root.iter():
        if element.tag in OBJECT_TAGS:
            nv = _c_nv_pr(element)
            if nv is not None:
                name = nv.get("name", "")
                if name:
                    names.append(name)
    return names


def _slide_text(root: ET.Element) -> str:
    parts = [text for element in root.iter() for text in [element.text or ""] if text.strip()]
    return "\n".join(parts)


def _slide_size(path: Path) -> tuple[int, int]:
    with zipfile.ZipFile(path) as archive:
        presentation_root = ET.fromstring(archive.read("ppt/presentation.xml"))
        sld_sz = presentation_root.find(f"{{{PRESENTATION_NS}}}sldSz")
        if sld_sz is None:
            raise RuntimeError("presentation.xml has no sldSz")
        return int(sld_sz.get("cx", "0")), int(sld_sz.get("cy", "0"))


def _chart_signature(path: Path) -> list[dict[str, Any]]:
    """Semantic signature of every embedded chart: type + categories + series names + values + number format."""
    signatures: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        chart_names = sorted(name for name in archive.namelist() if re.match(r"^ppt/charts/chart\d+\.xml$", name))
        for chart_name in chart_names:
            root = ET.fromstring(archive.read(chart_name))
            plot = root.find(f".//{{{CHART_NS}}}plotArea/*")
            chart_type = plot.tag.rsplit("}", 1)[-1] if plot is not None else None
            categories = [item.text or "" for item in root.findall(f".//{{{CHART_NS}}}cat/{{{CHART_NS}}}strRef/{{{CHART_NS}}}strCache/{{{CHART_NS}}}pt/{{{CHART_NS}}}v") + root.findall(f".//{{{CHART_NS}}}cat/{{{CHART_NS}}}strLit/{{{CHART_NS}}}pt/{{{CHART_NS}}}v")]
            values = [item.text or "" for item in root.findall(f".//{{{CHART_NS}}}val/{{{CHART_NS}}}numRef/{{{CHART_NS}}}numCache/{{{CHART_NS}}}pt/{{{CHART_NS}}}v") + root.findall(f".//{{{CHART_NS}}}val/{{{CHART_NS}}}numLit/{{{CHART_NS}}}pt/{{{CHART_NS}}}v")]
            series_names = [item.text or "" for item in root.findall(f".//{{{CHART_NS}}}ser/{{{CHART_NS}}}tx/{{{CHART_NS}}}strRef/{{{CHART_NS}}}strCache/{{{CHART_NS}}}pt/{{{CHART_NS}}}v") + root.findall(f".//{{{CHART_NS}}}ser/{{{CHART_NS}}}tx/{{{CHART_NS}}}strLit/{{{CHART_NS}}}pt/{{{CHART_NS}}}v")]
            num_formats = [item.get("formatCode", "") for item in root.findall(f".//{{{CHART_NS}}}numFmt")]
            signatures.append({"chart": chart_name, "type": chart_type, "categories": categories, "series_names": series_names, "values": values, "number_formats": num_formats})
    return signatures


def _workbook_signature(path: Path) -> list[dict[str, Any]]:
    """Embedded workbook cell semantics: per-sheet cell value sequences (semantic, not byte comparison)."""
    signatures: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        for sheet_name in sorted(name for name in archive.namelist() if re.match(r"^xl/worksheets/sheet\d+\.xml$", name)):
            root = ET.fromstring(archive.read(sheet_name))
            cells: list[dict[str, str | None]] = []
            for cell in root.findall(f".//{{{SHEET_NS}}}c"):
                value = cell.find(f"{{{SHEET_NS}}}v")
                cells.append({"ref": cell.get("r", ""), "value": value.text if value is not None else None})
            signatures.append({"sheet": sheet_name, "cells": cells})
    return signatures


def _media_signature(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return sorted(name for name in archive.namelist() if name.startswith("ppt/media/"))


def _structural_snapshot(path: Path, manifest_slides: list[dict[str, Any]]) -> dict[str, Any]:
    """Slide identity is manifest-driven: slideN.xml order is mapped through the P4 manifest,
    and each page is identified by its cNvPr objectName set (Expected Element IDs), not object counts."""
    with zipfile.ZipFile(path) as archive:
        names = _slide_names(archive)
        if len(names) != len(manifest_slides):
            return {"valid": False, "error": f"slide count {len(names)} != manifest {len(manifest_slides)}"}
        slides: list[dict[str, Any]] = []
        for index, name in enumerate(names):
            root = ET.fromstring(archive.read(name))
            slides.append({
                "order": index + 1,
                "object_names": _slide_object_names(root),
                "text": _slide_text(root),
                "chart_frames": len([element for element in root.iter() if element.tag == f"{{{NS['p']}}}graphicFrame"]),
            })
        return {"valid": True, "slides": slides}


def _com_worker(argv: list[str]) -> int:
    """Worker: open the roundtrip copy, SaveAs a second copy, render the saved copy through PowerPoint COM."""
    src, saved_path, render_dir, width, height, state = Path(argv[0]), Path(argv[1]), Path(argv[2]), int(argv[3]), int(argv[4]), Path(argv[5])
    app = presentation = reopened = None
    try:
        import pythoncom
        import win32api
        import win32com.client
        pythoncom.CoInitialize()
        app = win32com.client.DispatchEx("PowerPoint.Application")
        presentation = app.Presentations.Open(str(src.resolve()), ReadOnly=False, Untitled=False, WithWindow=False)
        presentation.SaveAs(str(saved_path.resolve()))
        presentation.Close()
        presentation = None
        render_dir.mkdir(parents=True, exist_ok=True)
        reopened = app.Presentations.Open(str(saved_path.resolve()), ReadOnly=True, Untitled=False, WithWindow=False)
        for index in range(1, reopened.Slides.Count + 1):
            reopened.Slides(index).Export(str((render_dir / f"slide-{index:03d}.png").resolve()), "PNG", width, height)
        executable = Path(app.Path) / "POWERPNT.EXE"
        file_version = None
        if executable.is_file():
            try:
                info = win32api.GetFileVersionInfo(str(executable), "\\")
                file_version = ".".join(str(value) for value in (info["FileVersionMS"] >> 16, info["FileVersionMS"] & 0xFFFF, info["FileVersionLS"] >> 16, info["FileVersionLS"] & 0xFFFF))
            except Exception:
                pass
        state.write_text(json.dumps({"status": "passed", "version": f"COM {app.Version}" + (f"; file {file_version}" if file_version else ""), "slide_count": reopened.Slides.Count}), encoding="utf-8")
        return 0
    except Exception as exc:
        state.write_text(json.dumps({"status": "failed", "message": str(exc)}), encoding="utf-8")
        return 1
    finally:
        if reopened is not None:
            try: reopened.Close()
            except Exception: pass
        if presentation is not None:
            try: presentation.Close()
            except Exception: pass
        if app is not None:
            try: app.Quit()
            except Exception: pass
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _canonicalize(path: Path, width: int, height: int) -> None:
    with Image.open(path) as image:
        image.load()
        if image.size != (width, height):
            raise RuntimeError("PowerPoint render size mismatch")
        stream = io.BytesIO()
        image.convert("RGB").save(stream, format="PNG", optimize=False, compress_level=9)
        path.write_bytes(stream.getvalue())


def run_roundtrip(*, deck_id: str, candidate_pptx: Path, p4_manifest: dict[str, Any], output: Path, width_px: int, height_px: int, timeout_seconds: int = 240) -> dict[str, Any]:
    manifest_slides = sorted(p4_manifest.get("slides", []), key=lambda item: item["order"])
    original_snapshot = _structural_snapshot(candidate_pptx, manifest_slides)
    original_size = _slide_size(candidate_pptx)
    original_charts = _chart_signature(candidate_pptx)
    original_workbooks = _workbook_signature(candidate_pptx)
    original_media = _media_signature(candidate_pptx)
    failures: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix=".p5-roundtrip-", dir=candidate_pptx.parent) as temporary:
        stage = Path(temporary)
        copy_path = stage / "roundtrip-copy.pptx"
        saved_path = stage / "roundtrip-saved.pptx"
        shutil.copy2(candidate_pptx, copy_path)
        rendered = stage / "rendered"
        state = stage / "state.json"
        command = [sys.executable, str(Path(__file__).resolve()), "--_worker", str(copy_path), str(saved_path), str(rendered), str(width_px), str(height_px), str(state)]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_seconds, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        details = json.loads(state.read_text(encoding="utf-8")) if state.exists() else {}
        if completed.returncode or details.get("status") != "passed":
            raise ContractError([error("$.roundtrip", details.get("message") or completed.stderr or "PowerPoint roundtrip failed", "roundtrip_failed")])

        saved_snapshot = _structural_snapshot(saved_path, manifest_slides)
        saved_size = _slide_size(saved_path)
        saved_charts = _chart_signature(saved_path)
        saved_workbooks = _workbook_signature(saved_path)
        saved_media = _media_signature(saved_path)

        structural = {
            "slide_count_same": original_snapshot.get("valid") and saved_snapshot.get("valid"),
            "slide_order_same": original_snapshot.get("valid") and saved_snapshot.get("valid") and [item["object_names"] for item in original_snapshot["slides"]] == [item["object_names"] for item in saved_snapshot["slides"]],
            "slide_size_same": original_size == saved_size,
        }
        canonical_text_same = [item["text"] for item in original_snapshot["slides"]] == [item["text"] for item in saved_snapshot["slides"]]
        element_counts_same = [len(item["object_names"]) for item in original_snapshot["slides"]] == [len(item["object_names"]) for item in saved_snapshot["slides"]]
        chart_data_same = original_charts == saved_charts
        workbook_data_same = original_workbooks == saved_workbooks
        media_same = original_media == saved_media
        if not all(structural.values()):
            failures.append(error("$.structural_comparison", "roundtrip structural comparison failed", "roundtrip_structural_drift"))
        if not canonical_text_same:
            failures.append(error("$.canonical_text_same", "roundtrip canonical text drift", "roundtrip_semantic_drift"))
        if not element_counts_same:
            failures.append(error("$.element_counts_same", "roundtrip element count drift", "roundtrip_structural_drift"))
        if not chart_data_same:
            failures.append(error("$.chart_data_same", "roundtrip chart semantic signature drift", "roundtrip_semantic_drift"))
        if not workbook_data_same:
            failures.append(error("$.workbook_data_same", "roundtrip embedded workbook cell drift", "roundtrip_semantic_drift"))
        if not media_same:
            failures.append(error("$.media_same", "roundtrip media set drift", "roundtrip_structural_drift"))

        external_relationships = 0
        macro_ole = 0
        with zipfile.ZipFile(saved_path) as archive:
            names = archive.namelist()
            if any(name.endswith("vbaProject.bin") or name.startswith("ppt/ole") for name in names):
                macro_ole += 1
            for name in names:
                if not name.endswith(".rels"):
                    continue
                rel_root = ET.fromstring(archive.read(name))
                for rel in rel_root:
                    target = rel.get("Target", "")
                    mode = rel.get("TargetMode", "Internal")
                    if mode == "External" or target.startswith(("http://", "https://", "ftp://", "file:", "mailto:")) or target.startswith("\\") or re.match(r"^[a-zA-Z]:[/\\]", target):
                        external_relationships += 1
        relationship_safety = "safe" if external_relationships == 0 and macro_ole == 0 else "unsafe"
        if relationship_safety != "safe":
            failures.append(error("$.relationship_safety", "roundtrip saved copy contains unsafe relationships", "roundtrip_unsafe_relationships"))

        # Render the ORIGINAL candidate through the same PowerPoint pipeline for pixel comparison.
        original_render_dir = stage / "original-render"
        original_report_path = stage / "original-render-report.json"
        original_command = [sys.executable, str(Path(__file__).resolve().parent / "render_reconstruction_deck.py"), "--input", str(candidate_pptx.resolve()), "--output-dir", str(original_render_dir), "--report", str(original_report_path), "--width-px", str(width_px), "--height-px", str(height_px)]
        original_completed = subprocess.run(original_command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_seconds, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if original_completed.returncode:
            raise ContractError([error("$.render_original", original_completed.stdout.strip() or original_completed.stderr.strip(), "roundtrip_failed")])

        files = sorted(rendered.glob("slide-*.png"))
        original_files = sorted(original_render_dir.glob("slide-*.png"))
        if len(files) != len(manifest_slides) or len(original_files) != len(manifest_slides):
            failures.append(error("$.render", "roundtrip render slide count mismatch", "roundtrip_structural_drift"))
        slides: list[dict[str, Any]] = []
        for index, item in enumerate(files, 1):
            _canonicalize(item, width_px, height_px)
            original = original_files[index - 1] if index - 1 < len(original_files) else None
            original_decoded = decoded_rgb_sha256(original) if original is not None and original.is_file() else ""
            roundtrip_decoded = decoded_rgb_sha256(item)
            pixel_same = original_decoded == roundtrip_decoded
            if original_decoded and not pixel_same:
                failures.append(error(f"$.slides[{index}].decoded_rgb_same", "roundtrip decoded pixel drift", "roundtrip_pixel_drift"))
            slides.append({"order": index, "decoded_rgb_same": pixel_same, "original_decoded_rgb_sha256": original_decoded, "roundtrip_decoded_rgb_sha256": roundtrip_decoded})

        report = {
            "schema_version": "1.0",
            "artifact_type": "powerpoint_roundtrip_report",
            "deck_id": deck_id,
            "roundtrip_copy_sha256": file_sha256(saved_path),
            "structural_comparison": structural,
            "canonical_text_same": canonical_text_same,
            "element_counts_same": element_counts_same,
            "chart_data_same": chart_data_same,
            "workbook_data_same": workbook_data_same,
            "media_same": media_same,
            "relationship_safety": relationship_safety,
            "external_relationships": external_relationships,
            "macro_ole": macro_ole,
            "slides": slides,
            "status": "fail" if failures else "pass",
        }
    if failures:
        raise ContractError(failures)
    validate_schema("powerpoint_roundtrip_report", report, SCHEMA_DIR)
    return report


def main() -> int:
    args = parser().parse_args()
    try:
        from schema_utils import load_json
        manifest = load_json(args.p4_manifest)
        report = run_roundtrip(deck_id=args.deck_id, candidate_pptx=args.candidate_pptx, p4_manifest=manifest, output=args.output, width_px=args.width_px, height_px=args.height_px, timeout_seconds=args.timeout_seconds)
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"status": "ok", "outputs": {"report": str(output), "roundtrip_status": report["status"]}, "error": None}, ensure_ascii=False))
        return 0
    except Exception as exc:
        issues = exc.errors if isinstance(exc, ContractError) else [{"path": "$", "code": "roundtrip_internal_error", "message": str(exc)}]
        print(json.dumps({"status": "error", "outputs": {}, "error": {"issues": issues}}, ensure_ascii=False))
        return 4 if isinstance(exc, ContractError) else 70


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--_worker":
        raise SystemExit(_com_worker(sys.argv[2:]))
    raise SystemExit(main())
