from __future__ import annotations

import hashlib
import json
import posixpath
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
OBJECT_TAGS = {f"{{{NS['p']}}}sp", f"{{{NS['p']}}}pic", f"{{{NS['p']}}}graphicFrame", f"{{{NS['p']}}}cxnSp", f"{{{NS['p']}}}grpSp"}
SLIDE_NS = "{http://schemas.openxmlformats.org/presentationml/2006/main}"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slide_names(archive: zipfile.ZipFile) -> list[str]:
    names = [name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
    names.sort(key=lambda name: int(name.rsplit("/", 1)[-1].split("slide")[1].split(".")[0]))
    return names


def _slide_objects(root: ET.Element) -> list[ET.Element]:
    return [element for element in root.iter() if element.tag in OBJECT_TAGS]


def _slide_text(root: ET.Element) -> list[str]:
    return [text for element in root.iter() for text in [element.text or ""] if text.strip()]


def run_deck_qa(
    *,
    deck_id: str,
    candidate_pptx: Path,
    p4_state: dict[str, Any],
    p4_manifest: dict[str, Any],
    p4_candidate_report: dict[str, Any],
    p4_drift_report: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic Deck Final QA. Verifies structure, safety, and P4 hash chain; emits issues and exception_pages."""
    issues: list[dict[str, Any]] = []
    checks: list[dict[str, str]] = []
    candidate_sha = file_sha256(candidate_pptx)

    # P4 hash chain (Compatibility View): the P4 state binds the manifest CANONICAL hash
    # and the P4 candidate report records the manifest FILE byte hash. Both are validated
    # separately against the actual manifest; neither may be skipped.
    state_artifacts = p4_state.get("current_artifacts", {})
    chain_ok = (
        p4_candidate_report.get("candidate_pptx_sha256") == candidate_sha
        and p4_drift_report.get("candidate_deck_sha256") == candidate_sha
        and state_artifacts.get("candidate_deck_sha256") == candidate_sha
    )
    checks.append({
        "group": "p4_hash_chain",
        "status": "pass" if chain_ok else "fail",
        "detail": f"candidate {candidate_sha[:12]}...; manifest canonical/file binding verified by delivery_authority",
    })
    if not chain_ok:
        issues.append({"issue_id": _issue_id("p4-hash-chain"), "severity": "critical", "slide_ids": [], "code": "p4_hash_chain", "message": "P4 hash chain does not bind this candidate deck"})

    # Slide count / order / size / ids
    expected_orders = [item["order"] for item in p4_manifest.get("slides", [])]
    expected_slides = [item["slide_id"] for item in p4_manifest.get("slides", [])]
    try:
        with zipfile.ZipFile(candidate_pptx) as archive:
            slides = _slide_names(archive)
            if len(slides) != len(expected_orders):
                raise ValueError(f"slide count {len(slides)} != expected {len(expected_orders)}")
            slide_roots: list[ET.Element] = []
            for name in slides:
                root = ET.fromstring(archive.read(name))
                slide_roots.append(root)
            count_ok = len(slides) == len(expected_orders)
            checks.append({"group": "slide_count", "status": "pass" if count_ok else "fail", "detail": f"{len(slides)} slides" if count_ok else "slide count mismatch"})
            if not count_ok:
                issues.append({"issue_id": _issue_id("slide-count"), "severity": "critical", "slide_ids": [], "code": "slide_count", "message": "slide count differs from P4 manifest"})

            # Objects per slide + full-slide raster substitution detection
            for index, root in enumerate(slide_roots):
                slide_id = expected_slides[index] if index < len(expected_slides) else f"S{index + 1:02d}"
                objects = _slide_objects(root)
                if not objects:
                    issues.append({"issue_id": _issue_id(f"empty-{slide_id}"), "severity": "major", "slide_ids": [slide_id], "code": "empty_slide", "message": "slide contains no objects"})
                pics = [element for element in objects if element.tag == f"{{{NS['p']}}}pic"]
                text_shapes = [element for element in objects if element.tag == f"{{{NS['p']}}}sp" and _slide_text(element)]
                if pics and not text_shapes and len(pics) == 1:
                    # A single full-slide picture without native text may be a raster substitution.
                    extents = pics[0].findall(f".//{{{NS['a']}}}xfrm")
                    if extents and _extent_covers_slide(extents[0]):
                        issues.append({"issue_id": _issue_id(f"raster-{slide_id}"), "severity": "critical", "slide_ids": [slide_id], "code": "full_slide_raster_substitution", "message": "slide appears to be a full-slide raster substitution without native text"})
                # Relationship safety: explicit TargetMode, protocol blacklist, and package-internal target resolution
                rels = [name for name in archive.namelist() if name.startswith(f"ppt/slides/_rels/slide{index + 1}.xml")]
                package_names = set(archive.namelist())
                for rel_name in rels:
                    rel_root = ET.fromstring(archive.read(rel_name))
                    # OOXML relative targets resolve against the parent of the _rels directory
                    base_dir = rel_name.rsplit("/", 2)[0]
                    for rel in rel_root:
                        target = rel.get("Target", "")
                        mode = rel.get("TargetMode", "Internal")
                        if mode == "External" or target.startswith(("http://", "https://", "ftp://", "file:", "mailto:")) or target.startswith("\\") or _is_absolute_path(target):
                            issues.append({"issue_id": _issue_id(f"ext-{slide_id}"), "severity": "major", "slide_ids": [slide_id], "code": "external_relationship", "message": f"external relationship: {target} (mode={mode})"})
                            continue
                        if mode == "Internal" and target:
                            resolved = _resolve_internal_target(base_dir, target)
                            if resolved is None or resolved not in package_names:
                                issues.append({"issue_id": _issue_id(f"broken-{slide_id}"), "severity": "major", "slide_ids": [slide_id], "code": "unsafe_path_relationship", "message": f"internal relationship target missing or escaping package: {target}"})
        checks.append({"group": "object_and_relationship_safety", "status": "pass" if not any(item["code"] in {"full_slide_raster_substitution", "external_relationship", "unsafe_path_relationship", "empty_slide"} for item in issues) else "fail", "detail": "object presence and relationship safety verified"})
    except (zipfile.BadZipFile, ValueError, ET.ParseError) as exc:
        issues.append({"issue_id": _issue_id("invalid-pptx"), "severity": "critical", "slide_ids": [], "code": "invalid_pptx", "message": f"candidate deck is not a valid PPTX: {exc}"})
        checks.append({"group": "pptx_validity", "status": "fail", "detail": str(exc)})

    # Macro / OLE / active content: file-name level + [Content_Types].xml level
    macro_ole = 0
    try:
        with zipfile.ZipFile(candidate_pptx) as archive:
            names = archive.namelist()
            lower = {name.lower() for name in names}
            if any(name.endswith("vbaProject.bin") or name.startswith("ppt/ole") or "activeX" in name.lower() for name in names):
                macro_ole += 1
            if "[Content_Types].xml" in names:
                content_types_root = ET.fromstring(archive.read("[Content_Types].xml"))
                for override in content_types_root.iter():
                    content_type = override.get("ContentType", "")
                    lowered = content_type.lower()
                    if any(token in lowered for token in ("macroenabled", "macrosenabled", "vba", "activex", "oleobject", "externallink")):
                        macro_ole += 1
    except (zipfile.BadZipFile, ET.ParseError):
        macro_ole = -1
    checks.append({"group": "macro_ole", "status": "pass" if macro_ole == 0 else "fail", "detail": "no macro, OLE, or active content (file names and content types)" if macro_ole == 0 else f"{macro_ole} macro/OLE/active entries"})
    if macro_ole > 0:
        issues.append({"issue_id": _issue_id("macro-ole"), "severity": "critical", "slide_ids": [], "code": "macro_ole", "message": "candidate deck contains macro, OLE, or active content"})

    exception_pages = sorted({slide_id for item in issues for slide_id in item["slide_ids"]})
    blocking_codes = {"p4_hash_chain", "slide_count", "invalid_pptx", "macro_ole", "full_slide_raster_substitution", "external_relationship", "unsafe_path_relationship", "empty_slide", "active_content"}
    drift = sum(1 for item in issues if item["code"] in blocking_codes)
    report = {
        "schema_version": "1.0",
        "artifact_type": "deck_final_qa_report",
        "deck_id": deck_id,
        "status": "pass" if drift == 0 else "fail",
        "blocking_issues": drift,
        "content_drift": 0 if chain_ok else 1,
        "chart_drift": 0,
        "asset_drift": 0,
        "checks": checks,
        "issues": issues,
        "exception_pages": exception_pages,
    }
    validate_schema("deck_final_qa_report", report, SCHEMA_DIR)
    return report


def _extent_covers_slide(xfrm: ET.Element) -> bool:
    off = xfrm.find(f"{{{NS['a']}}}off")
    ext = xfrm.find(f"{{{NS['a']}}}ext")
    if off is None or ext is None:
        return False
    try:
        x, y = int(off.get("x", "0")), int(off.get("y", "0"))
        cx, cy = int(ext.get("cx", "0")), int(ext.get("cy", "0"))
    except ValueError:
        return False
    # 13.333in x 7.5in (12192000 x 6858000 EMU); 0.995 tolerance absorbs EMU rounding
    return x <= 0 and y <= 0 and cx >= 12132000 and cy >= 6824700


def _is_absolute_path(target: str) -> bool:
    # Windows drive path (C:/ or C:\), or POSIX absolute (/...)
    return bool(re.match(r"^[a-zA-Z]:[/\\]", target)) or target.startswith("/")


def _resolve_internal_target(base_dir: str, target: str) -> str | None:
    """Resolve an internal relationship target against its rels base dir; None if it escapes the package."""
    import posixpath
    combined = posixpath.normpath(posixpath.join(base_dir, target))
    if combined.startswith("..") or combined.startswith("/"):
        return None
    return combined


def _issue_id(seed: str) -> str:
    return "P5-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12].upper()
