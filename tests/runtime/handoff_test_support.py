from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def request(source_image: str = "source.png") -> dict:
    return {
        "schema_version": "1.3",
        "task_id": "p2-handoff",
        "topic": "P2 Handoff",
        "source_image": source_image,
        "output_ratio": "16:9",
        "typography_interaction": "default",
        "typography": {
            "title_font": "Microsoft YaHei",
            "title_size_pt": 28,
            "body_font": "Microsoft YaHei",
            "body_size_pt": 16,
        },
        "editability_policy": "text-and-structure",
        "user_requirements": [],
        "review_policy": {
            "max_iterations": 1,
            "pass_score": 90,
            "warning_floor_score": 85,
            "min_content_accuracy": 98,
            "required_editability_score": 100,
            "critical_policy": "by_recoverability",
        },
    }


def stage1_authority() -> dict:
    return {
        "schema_version": "1.0",
        "status": "approved",
        "deck_id": "deck_001",
        "brief": {
            "topic": "Visual-first",
            "audience": "Developers",
            "objective": "Explain the handoff",
            "presentation_type": "technical",
            "language": "zh-CN",
        },
        "slides": [
            {
                "slide_id": "S01",
                "order": 1,
                "section": "Architecture",
                "role": "overview",
                "key_message": "Approved semantics survive visual design.",
                "source_refs": ["brief-01"],
                "visual_need": "Two connected cards and a chart.",
                "wireframe": {"path": "wireframes/S01.md", "sha256": "0" * 64},
                "text_items": [
                    {"id": "S01-title", "role": "title", "text": "Deterministic Handoff"}
                ],
                "objects": [
                    {"id": "title-object", "kind": "text", "role": "title", "content_ref": "S01-title"},
                    {"id": "card-01", "kind": "shape", "role": "step"},
                    {"id": "card-02", "kind": "shape", "role": "step"},
                    {"id": "connector-01", "kind": "connector", "role": "flow", "relation_ref": "relation-01"},
                    {"id": "chart-01", "kind": "chart", "role": "evidence", "data_ref": "data-chart-01"},
                    {"id": "table-01", "kind": "table", "role": "detail", "data_ref": "data-table-01"},
                ],
                "semantic_structure": {
                    "regions": [
                        {"id": "region-main", "role": "main_content", "members": ["card-01", "card-02", "chart-01", "table-01"]}
                    ],
                    "reading_order": ["title-object", "card-01", "card-02", "chart-01", "table-01"],
                    "relations": [
                        {"id": "relation-01", "kind": "sequence", "from_id": "card-01", "to_id": "card-02"}
                    ],
                },
                "structured_data": [
                    {
                        "id": "data-chart-01",
                        "kind": "chart",
                        "categories": ["Experimental", "Control"],
                        "series": [{"name": "Posttest", "values": [79.5, 73.78]}],
                    },
                    {
                        "id": "data-table-01",
                        "kind": "table",
                        "columns": ["Group", "Mean"],
                        "rows": [["Experimental", 79.5], ["Control", 73.78]],
                    },
                ],
            }
        ],
    }


def stage2_handoff(stage1_sha256: str) -> dict:
    return {
        "schema_version": "1.0",
        "status": "approved",
        "deck_id": "deck_001",
        "stage1_authority_sha256": stage1_sha256,
        "slides": [
            {
                "slide_id": "S01",
                "approved_design": {"path": "designs/S01.png", "sha256": "0" * 64},
                "visual_spec": {"path": "visual-specs/S01.json", "sha256": "0" * 64},
                "visual_objects": [
                    {
                        "id": "visual-hero-01",
                        "role": "hero_illustration",
                        "description": "Right-side abstract visual",
                        "handling": {
                            "independent_crop": True,
                            "independent_positioning": True,
                            "z_order_sensitive": True
                        },
                        "overlaps_with": ["card-01"],
                    }
                ],
            }
        ],
    }


def write_approved_artifacts(root: Path, sha256_file) -> tuple[Path, Path]:
    stage1_root = root / "stage1"
    stage2_root = root / "stage2"
    (stage1_root / "wireframes").mkdir(parents=True)
    (stage2_root / "designs").mkdir(parents=True)
    (stage2_root / "visual-specs").mkdir(parents=True)
    wireframe = stage1_root / "wireframes" / "S01.md"
    wireframe.write_bytes(b"# S01\n\n[title] -> [cards]\n")
    Image.new("RGB", (1600, 900), "#7CB9E8").save(stage2_root / "designs" / "S01.png")
    visual_spec = stage2_root / "visual-specs" / "S01.json"
    visual_spec.write_text(json.dumps({"visual_objective": "clarity"}, sort_keys=True), encoding="utf-8")

    stage1 = stage1_authority()
    stage1["slides"][0]["wireframe"]["sha256"] = sha256_file(wireframe)
    stage1_path = stage1_root / "stage1-authority.json"
    stage1_path.write_text(json.dumps(stage1, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    stage2 = stage2_handoff(sha256_file(stage1_path))
    stage2["slides"][0]["approved_design"]["sha256"] = sha256_file(stage2_root / "designs" / "S01.png")
    stage2["slides"][0]["visual_spec"]["sha256"] = sha256_file(visual_spec)
    stage2_path = stage2_root / "stage2-handoff.json"
    stage2_path.write_text(json.dumps(stage2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return stage1_path, stage2_path


def materializer_args(root: Path, schema_dir: Path, sha256_file, *, source_image: str = "source.png") -> argparse.Namespace:
    stage1_path, stage2_path = write_approved_artifacts(root, sha256_file)
    work_root = root / "work"
    work_root.mkdir()
    (work_root / "request.json").write_text(json.dumps(request(source_image), ensure_ascii=False), encoding="utf-8")
    return argparse.Namespace(
        stage1_authority=stage1_path,
        stage2_handoff=stage2_path,
        slide_id="S01",
        work_root=work_root,
        schema_dir=schema_dir,
        force=False,
    )
