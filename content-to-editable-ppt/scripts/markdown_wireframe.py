from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from canonical_artifact import canonical_sha256
from deterministic_project_slide_content import verify_projection
from schema_utils import ContractError, error, is_safe_relative_path, load_json, validate_schema


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
CANONICALIZATION_VERSION = "p1-rfc8785-nfc-1"
CONTENT_TOKEN = re.compile(r"\{\{p2:content-ref=([^{}]+)\}\}")
ZONE_TOKEN = re.compile(r"\{\{p2:zone=(image|chart|diagram|process|timeline|icon|decoration|whitespace)\}\}")
SLIDE_MARKER = re.compile(r"<!-- p2:slide-id=([^\s]+) -->")
CONTENT_BLOCK = re.compile(
    r"<!-- p2:content-ref=([^\s]+):start -->\n(.*?)\n<!-- p2:content-ref=\1:end -->",
    re.DOTALL,
)
FORBIDDEN_TEXT = re.compile(r"(?is)<!--|-->|```|<script\b|javascript:|(?:https?|file|data):|\\\\|[A-Za-z]:\\")
NON_STRUCTURAL = re.compile(r"[A-Za-z0-9\u3400-\u9fff]")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def authority_items(slide: dict[str, Any]) -> list[dict[str, Any]]:
    return [slide["title"], *sorted(slide["content_blocks"], key=lambda item: item["order"])]


def load_markdown_authority(
    *, p1_state_path: Path, approved_outline_path: Path, slide_content_dir: Path
) -> dict[str, Any]:
    p1_state = load_json(p1_state_path)
    approved = load_json(approved_outline_path)
    validate_schema("content_plan_state", p1_state, SCHEMA_DIR)
    validate_schema("approved_outline", approved, SCHEMA_DIR)
    failures: list[dict[str, str]] = []
    if p1_state["state"] != "p1_complete":
        failures.append(error("$.p1_state.state", "P2 requires p1_complete", "p1_not_complete"))
    if p1_state["deck_id"] != approved["deck_id"]:
        failures.append(error("$.approved_outline.deck_id", "Authority Bundle deck_id mismatch", "deck_mismatch"))
    outline_sha = canonical_sha256(approved)
    frozen_outline = p1_state["current_artifacts"].get("approved_outline_sha256")
    if frozen_outline is None:
        failures.append(error("$.p1_state.current_artifacts.approved_outline_sha256", "P1 State has no frozen Approved Outline", "missing_authority"))
    elif frozen_outline != outline_sha:
        failures.append(error("$.p1_state.current_artifacts.approved_outline_sha256", "Approved Outline does not match P1 State", "authority_hash_mismatch"))

    projection_path = slide_content_dir / "projection-manifest.json"
    try:
        projection = load_json(projection_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ContractError):
        projection = None
        failures.append(error("$.slide_content_manifest", "projection-manifest.json is missing or unreadable", "missing_authority"))
    contents: dict[str, dict[str, Any]] = {}
    if projection is not None:
        actual_projection = canonical_sha256(projection)
        frozen_projection = p1_state["current_artifacts"].get("slide_content_manifest_sha256")
        if frozen_projection is None:
            failures.append(error("$.p1_state.current_artifacts.slide_content_manifest_sha256", "P1 State has no frozen Projection Manifest", "missing_authority"))
        elif frozen_projection != actual_projection:
            failures.append(error("$.p1_state.current_artifacts.slide_content_manifest_sha256", "Projection Manifest does not match P1 State", "authority_hash_mismatch"))
        if projection.get("deck_id") != approved["deck_id"] or projection.get("approved_outline_sha256") != outline_sha:
            failures.append(error("$.slide_content_manifest", "Projection Manifest does not bind Approved Outline", "authority_hash_mismatch"))
        for index, item in enumerate(projection.get("slides", [])):
            relative = item.get("path", "")
            base = f"$.slide_content_manifest.slides[{index}]"
            if not is_safe_relative_path(relative):
                failures.append(error(base + ".path", "unsafe slide content path", "unsafe_path"))
                continue
            try:
                content = load_json(slide_content_dir / relative)
                validate_schema("approved_slide_content", content, SCHEMA_DIR)
            except (OSError, UnicodeError, json.JSONDecodeError, ContractError):
                failures.append(error(base + ".path", "slide content is missing or invalid", "missing_authority"))
                continue
            if canonical_sha256(content) != item.get("sha256"):
                failures.append(error(base + ".sha256", "slide content hash mismatch", "authority_hash_mismatch"))
            else:
                try:
                    verify_projection(approved, content)
                except ContractError as exc:
                    failures.extend(exc.errors)
            if content.get("deck_id") != approved["deck_id"] or content.get("slide_id") in contents:
                failures.append(error(base, "duplicate or cross-deck slide content", "slide_set_mismatch"))
            else:
                contents[content["slide_id"]] = content
    pages = {page["slide_id"]: page for page in approved["pages"]}
    if set(contents) != set(pages):
        failures.append(error("$.slide_content_manifest.slides", "Slide Content IDs must exactly match Approved Outline", "slide_set_mismatch"))
    for slide_id in set(contents) & set(pages):
        if contents[slide_id]["order"] != pages[slide_id]["order"]:
            failures.append(error(f"$.slide_content.{slide_id}.order", "Slide order differs from Approved Outline", "order_mismatch"))
    if failures:
        raise ContractError(failures)
    return {
        "p1_state": p1_state,
        "approved_outline": approved,
        "projection_manifest": projection,
        "slide_contents": contents,
    }


def _issue(index: int, *, slide_id: str | None, code: str, path: str, message: str, blocking: bool = False) -> dict[str, Any]:
    return {
        "issue_id": f"P2M-{index:03d}",
        "slide_id": slide_id,
        "classification": "blocking_authority_error" if blocking else "correctable_contract_error",
        "code": code,
        "path": path,
        "message": message,
        "correctable": not blocking,
    }


def validate_candidate(candidate: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    validate_schema("markdown_wireframe_candidate", candidate, SCHEMA_DIR)
    problems: list[tuple[str | None, str, str, str, bool]] = []
    if candidate["deck_id"] != bundle["approved_outline"]["deck_id"]:
        problems.append((None, "deck_mismatch", "$.deck_id", "Candidate deck_id differs from P1 Authority", True))
    expected = sorted(bundle["slide_contents"].values(), key=lambda item: item["order"])
    actual_ids = [slide["slide_id"] for slide in candidate["slides"]]
    expected_ids = [slide["slide_id"] for slide in expected]
    if actual_ids != expected_ids:
        problems.append((None, "slide_sequence_mismatch", "$.slides", "Candidate slide IDs and order must exactly match P1 Authority", False))
    seen_ids: set[str] = set()
    for slide_index, slide in enumerate(candidate["slides"]):
        slide_id = slide["slide_id"]
        base = f"$.slides[{slide_index}]"
        if slide_id in seen_ids:
            problems.append((slide_id, "duplicate_slide", base + ".slide_id", "duplicate slide_id", False))
        seen_ids.add(slide_id)
        authority = bundle["slide_contents"].get(slide_id)
        if authority is None:
            problems.append((slide_id, "unknown_slide", base + ".slide_id", "slide_id is not present in P1 Authority", True))
            continue
        if slide["order"] != authority["order"]:
            problems.append((slide_id, "order_mismatch", base + ".order", "slide order differs from P1 Authority", False))
        refs = [item["content_ref"] for item in authority_items(authority)]
        labels = slide["content_labels"]
        label_refs = [item["content_ref"] for item in labels]
        if label_refs != refs:
            problems.append((slide_id, "content_label_sequence_mismatch", base + ".content_labels", "Content labels must exactly follow Authority order", False))
        label_map = {item["content_ref"]: normalize_text(item["label"]) for item in labels}
        for item in authority_items(authority):
            ref, text = item["content_ref"], normalize_text(item["text"])
            label = label_map.get(ref)
            if label is not None and label not in text:
                problems.append((slide_id, "label_not_authority_substring", base + ".content_labels", f"label for {ref} is not a continuous Authority substring", False))
        draft = normalize_text(slide["layout_draft"])
        if FORBIDDEN_TEXT.search(draft) or FORBIDDEN_TEXT.search(normalize_text(slide["layout_notes"])):
            problems.append((slide_id, "unsafe_candidate_text", base, "Candidate contains forbidden markup, script, path, or external reference", True))
        draft_refs = CONTENT_TOKEN.findall(draft)
        if draft_refs != refs:
            problems.append((slide_id, "content_placeholder_sequence_mismatch", base + ".layout_draft", "Layout draft must contain every Content Ref exactly once in Authority order", False))
        remainder = CONTENT_TOKEN.sub("", ZONE_TOKEN.sub("", draft))
        if "{{" in remainder or "}}" in remainder:
            problems.append((slide_id, "unknown_placeholder", base + ".layout_draft", "Layout draft contains an unknown placeholder", False))
        if NON_STRUCTURAL.search(remainder):
            problems.append((slide_id, "free_page_copy", base + ".layout_draft", "Layout draft may contain only structural glyphs and controlled placeholders", False))
    return [
        _issue(index, slide_id=item[0], code=item[1], path=item[2], message=item[3], blocking=item[4])
        for index, item in enumerate(problems, 1)
    ]


def build_validation_report(candidate: dict[str, Any], bundle: dict[str, Any], *, report_id: str, validated_at_utc: str | None = None) -> dict[str, Any]:
    issues = validate_candidate(candidate, bundle)
    status = "blocking" if any(not issue["correctable"] for issue in issues) else ("correctable" if issues else "pass")
    return {
        "schema_version": "1.0",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "artifact_type": "markdown_wireframe_validation_report",
        "report_id": report_id,
        "deck_id": candidate["deck_id"],
        "candidate_sha256": canonical_sha256(candidate),
        "status": status,
        "issues": issues,
        "validated_at_utc": validated_at_utc or utc_now(),
    }


def _render_slide(candidate_slide: dict[str, Any], authority: dict[str, Any]) -> str:
    labels = {item["content_ref"]: normalize_text(item["label"]) for item in candidate_slide["content_labels"]}
    draft = normalize_text(candidate_slide["layout_draft"])
    draft = CONTENT_TOKEN.sub(lambda match: labels[match.group(1)], draft)
    lines = [
        f"<!-- p2:slide-id={authority['slide_id']} -->",
        f"## 第 {authority['order']} 页｜{authority['slide_id']}",
        "",
        "### 页面内容",
        "",
    ]
    for index, item in enumerate(authority_items(authority)):
        label = "标题" if index == 0 else f"内容块 {index}"
        ref, text = item["content_ref"], normalize_text(item["text"])
        lines.extend([
            f"#### {label}",
            f"<!-- p2:content-ref={ref}:start -->",
            text,
            f"<!-- p2:content-ref={ref}:end -->",
            "",
        ])
    lines.extend([
        "### 布局线稿",
        "",
        "```text",
        draft,
        "```",
        "",
        "### 布局说明",
        "",
        normalize_text(candidate_slide["layout_notes"]),
    ])
    return "\n".join(lines)


def bind_markdown(candidate: dict[str, Any], bundle: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    issues = validate_candidate(candidate, bundle)
    if issues:
        raise ContractError([error(item["path"], item["message"], item["code"]) for item in issues])
    slides = sorted(candidate["slides"], key=lambda item: item["order"])
    markdown = ("\n\n---\n\n".join(
        _render_slide(slide, bundle["slide_contents"][slide["slide_id"]]) for slide in slides
    ) + "\n").encode("utf-8")
    manifest = {
        "schema_version": "1.0",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "artifact_type": "markdown_wireframe_manifest",
        "deck_id": candidate["deck_id"],
        "revision": candidate["revision"],
        "approved_outline_sha256": canonical_sha256(bundle["approved_outline"]),
        "slide_content_manifest_sha256": canonical_sha256(bundle["projection_manifest"]),
        "candidate_sha256": canonical_sha256(candidate),
        "wireframe_path": "deck-wireframe.md",
        "wireframe_sha256": sha256_bytes(markdown),
        "slides": [
            {
                "slide_id": slide["slide_id"],
                "order": slide["order"],
                "content_refs": [item["content_ref"] for item in authority_items(bundle["slide_contents"][slide["slide_id"]])],
            }
            for slide in slides
        ],
        "status": "ready_for_preview",
    }
    validate_schema("markdown_wireframe_manifest", manifest, SCHEMA_DIR)
    audit_markdown(markdown, manifest, bundle)
    return markdown, manifest


def audit_markdown(markdown: bytes, manifest: dict[str, Any], bundle: dict[str, Any]) -> None:
    try:
        text = markdown.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError([error("$.wireframe", "Markdown must be UTF-8", "markdown_encoding")]) from exc
    failures: list[dict[str, str]] = []
    if text.startswith("\ufeff") or "\r" in text or sha256_bytes(markdown) != manifest["wireframe_sha256"]:
        failures.append(error("$.wireframe", "Markdown encoding or hash is invalid", "markdown_hash_mismatch"))
    if SLIDE_MARKER.findall(text) != [item["slide_id"] for item in manifest["slides"]]:
        failures.append(error("$.wireframe", "Slide metadata differs from Manifest", "markdown_slide_mapping"))
    actual_blocks = CONTENT_BLOCK.findall(text)
    expected_blocks: list[tuple[str, str]] = []
    for slide in manifest["slides"]:
        expected_blocks.extend((item["content_ref"], normalize_text(item["text"])) for item in authority_items(bundle["slide_contents"][slide["slide_id"]]))
    if actual_blocks != expected_blocks:
        failures.append(error("$.wireframe", "Markdown content metadata or visible Authority text differs", "markdown_authority_drift"))
    if failures:
        raise ContractError(failures)


def clone_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(candidate)
