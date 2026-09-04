"""Read-only, byte-bound adapter shared by Canonical Revision entry points."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_common import REFERENCE_DIR, ensure_under
from asset_common import AssetError
from compile_reconstruction_plan import read_source_metadata
from evaluate_review import evaluate
from reconstruction_plan import compile_reconstruction_plan
from revision_patch import apply_patch, validate_patch, validate_plan_diff
from schema_utils import validate_schema, validate_semantics
from shared_validator import validate_documents
from visual_first_planner import content_authority_from_handoff, validate_plan_against_handoff


def require(condition: bool, message: str, code: str = "hash_conflict") -> None:
    if not condition:
        raise AssetError(message, code=code, exit_code=9)


@dataclass
class RevisionContext:
    work: Path
    current: Path
    schema_dir: Path
    snapshots: dict[Path, bytes] = field(default_factory=dict)
    documents: dict[str, Any] = field(default_factory=dict)

    def read(self, path: Path, *, root: Path | None = None) -> bytes:
        path = ensure_under(path, root or self.work)
        if path not in self.snapshots:
            require(path.is_file(), "required revision input is missing", "missing_input")
            self.snapshots[path] = path.read_bytes()
        return self.snapshots[path]

    def digest(self, path: Path, *, root: Path | None = None) -> str:
        return hashlib.sha256(self.read(path, root=root)).hexdigest()

    def document(self, path: Path, kind: str | None = None) -> dict[str, Any]:
        value = json.loads(self.read(path))
        require(isinstance(value, dict), "revision input must be an object", "contract_error")
        if kind:
            validate_schema(kind, value, self.schema_dir)
            validate_semantics(kind, value)
        return value

    def verify_unchanged(self) -> None:
        for path, content in self.snapshots.items():
            root = self.work if path.is_relative_to(self.work) else self.schema_dir if path.is_relative_to(self.schema_dir) else REFERENCE_DIR
            ensure_under(path, root)
            require(path.is_file() and path.read_bytes() == content, "revision input changed during validation")


def load_revision_context(work_root: Path, current_dir: Path, schema_dir: Path) -> RevisionContext:
    work = work_root.resolve()
    current = ensure_under(current_dir, work)
    require(current.parent == work / "iterations" and current.name.isdigit() and int(current.name) >= 1
            and current.name == f"{int(current.name):02d}" and current.is_dir(),
            "current directory must be a work-root iteration", "iteration_boundary")
    ctx = RevisionContext(work, current, schema_dir.resolve())
    for path in sorted(ctx.schema_dir.glob("*.schema.json")):
        ctx.read(path, root=ctx.schema_dir)
    d = ctx.documents
    d["request"] = ctx.document(work / "request.json", "request")
    d["handoff"] = ctx.document(work / "reconstruction-handoff.json", "reconstruction_handoff")
    d["base"] = ctx.document(current / "reconstruction-plan.json", "reconstruction_plan")
    request, handoff, base = d["request"], d["handoff"], d["base"]
    iteration = int(current.name)
    source = ensure_under(work / request["source_image"], work)
    d["source_path"] = source
    source_hash = ctx.digest(source)
    require(handoff["stage2"]["visual_spec"] == "visual-spec.json", "Visual Spec binding differs", "source_mismatch")
    d["visual_spec"] = ctx.document(work / "visual-spec.json")
    require(ctx.digest(work / "visual-spec.json") == handoff["provenance"]["visual_spec_sha256"], "Visual Spec changed")
    require(source_hash == handoff["provenance"]["approved_design_sha256"], "Approved Design changed")
    validate_plan_against_handoff(base, handoff, request, iteration=iteration, slide_id=handoff["slide_id"])
    if base["schema_version"] == "1.2":
        p = base["provenance"]
        require(p["reconstruction_handoff_sha256"] == ctx.digest(work / "reconstruction-handoff.json")
                and p["approved_design_sha256"] == source_hash, "baseline provenance differs from current inputs")
        require((p["previous_plan_sha256"] is None) == (p["revision_patch_sha256"] is None), "baseline provenance must be paired")
        if p["previous_plan_sha256"] is not None:
            require(iteration > 1, "initial iteration cannot have a previous plan", "iteration_mismatch")
            previous = current.parent / f"{iteration - 1:02d}" / "reconstruction-plan.json"
            require(ctx.digest(previous) == p["previous_plan_sha256"], "previous Plan hash mismatch")
            require(ctx.digest(current / "revision_patch.json") == p["revision_patch_sha256"], "previous Patch hash mismatch")
        else:
            require(iteration == 1, "revised Plan requires provenance chain", "iteration_mismatch")
    for key, kind, name in (("qa", "qa_report", "qa_report.json"), ("review", "review_report", "review_report.json"),
                            ("evaluation", "review_evaluation", "review_evaluation.json")):
        d[key] = ctx.document(current / name, kind)
        require((key == "qa" or d[key]["task_id"] == request["task_id"]) and d[key]["iteration"] == iteration,
                "review inputs do not match baseline task/iteration", "identity_mismatch")
    d["layout"] = ctx.document(current / "layout.json", "layout")
    d["asset_manifest"] = ctx.document(current / "asset_manifest.json", "asset_manifest")
    ctx.document(current / "crops.json", "crops")
    bindings = {
        "source_sha256": source_hash,
        "render_sha256": ctx.digest(current / "rendered_slide.png"),
        "layout_sha256": ctx.digest(current / "layout.json"),
        "qa_report_sha256": ctx.digest(current / "qa_report.json"),
        "asset_manifest_sha256": ctx.digest(current / "asset_manifest.json"),
        "request_sha256": ctx.digest(work / "request.json"),
        "review_rubric_sha256": ctx.digest(REFERENCE_DIR / "visual-review-rubric.md", root=REFERENCE_DIR),
        "reviewer_response_schema_sha256": ctx.digest(ctx.schema_dir / "reviewer-response.schema.json", root=ctx.schema_dir),
    }
    require(all(d["review"]["review_context"].get(key) == digest for key, digest in bindings.items()), "Review context is stale")
    qa_bindings = {key: bindings[key] for key in ("source_sha256", "render_sha256", "layout_sha256", "asset_manifest_sha256", "request_sha256")}
    qa_bindings["crops_sha256"] = ctx.digest(current / "crops.json")
    summary = ctx.document(current / "build_summary.json", "build_summary")
    qa_bindings["build_summary_sha256"] = ctx.digest(current / "build_summary.json")
    qa_bindings["ppt_sha256"] = ctx.digest(ensure_under(current / summary["output_pptx"], current))
    require(all(d["qa"]["provenance"].get(key) == digest for key, digest in qa_bindings.items()), "QA provenance is stale")
    expected = evaluate(request, d["qa"], d["review"], request_path=work / "request.json",
                        qa_path=current / "qa_report.json", review_path=current / "review_report.json")
    require(d["evaluation"] == expected, "Evaluation differs from deterministic evaluation", "evaluation_mismatch")
    require(d["evaluation"]["policy_decision"] == "revise", "Evaluation must request revision", "policy_conflict")
    d["source_metadata"] = read_source_metadata(source)
    compiled = compile_reconstruction_plan(base, content_authority_from_handoff(handoff), request, d["source_metadata"], handoff["structured_data"])
    require(compiled["layout"] == d["layout"] and compiled["crops"] == ctx.document(current / "crops.json"),
            "baseline Runtime does not match Canonical Plan", "baseline_runtime_mismatch")
    ctx.verify_unchanged()
    return ctx


def validate_revision(ctx: RevisionContext, patch: dict[str, Any], patch_sha256: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Run all candidate gates in memory without publishing an iteration."""
    d = ctx.documents
    validate_schema("revision_patch", patch, ctx.schema_dir)
    validate_semantics("revision_patch", patch)
    validate_patch(patch, d["base"], d["handoff"], d["review"], d["evaluation"], task_id=d["request"]["task_id"],
                   base_sha256=ctx.digest(ctx.current / "reconstruction-plan.json"),
                   review_sha256=ctx.digest(ctx.current / "review_report.json"),
                   evaluation_sha256=ctx.digest(ctx.current / "review_evaluation.json"))
    provenance = {"reconstruction_handoff_sha256": ctx.digest(ctx.work / "reconstruction-handoff.json"),
                  "approved_design_sha256": ctx.digest(d["source_path"]),
                  "previous_plan_sha256": ctx.digest(ctx.current / "reconstruction-plan.json"),
                  "revision_patch_sha256": patch_sha256}
    plan, _ = apply_patch(d["base"], patch, handoff_sha256=provenance["reconstruction_handoff_sha256"],
                          approved_design_sha256=provenance["approved_design_sha256"], patch_sha256=patch_sha256)
    diff = validate_plan_diff(d["base"], plan, patch, expected_provenance=provenance)
    validate_schema("reconstruction_plan", plan, ctx.schema_dir)
    validate_semantics("reconstruction_plan", plan)
    validate_plan_against_handoff(plan, d["handoff"], d["request"], iteration=patch["to_iteration"], slide_id=patch["page_id"])
    artifacts = compile_reconstruction_plan(plan, content_authority_from_handoff(d["handoff"]),
                                            d["request"], d["source_metadata"], d["handoff"]["structured_data"])
    validate_documents(artifacts, {}, profile="candidate", schema_dir=ctx.schema_dir)
    from finalize_agent_response import _validate_no_full_page_raster
    _validate_no_full_page_raster(artifacts["layout"], artifacts["crops"], artifacts["asset_manifest"])
    ctx.verify_unchanged()
    return plan, diff, artifacts
