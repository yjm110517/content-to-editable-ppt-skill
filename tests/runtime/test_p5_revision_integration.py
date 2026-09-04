from __future__ import annotations

import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch as mock_patch

from tests.runtime.p5_test_support import (
    ROOT, SCRIPTS, SCHEMAS, apply_args, atomic_write_json, create_work, fake_qa,
    load_json, make_patch, pipeline, sha256_file, sys, write_review,
)
from apply_revision_patch import apply_revision
from asset_common import AssetError, canonical_json_bytes
from revision_context import load_revision_context, validate_revision
from revision_patch import apply_patch, plan_diff, validate_plan_diff
from schema_utils import ContractError


def tree(path: Path) -> dict[str, bytes]:
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob("*") if p.is_file()}


class P5RevisionIntegrationTests(unittest.TestCase):
    def work(self, root: Path, **kwargs) -> Path:
        work = create_work(root, **kwargs)
        fake_qa(work)
        write_review(work)
        atomic_write_json(apply_args(work).patch, make_patch(work))
        return work

    def test_apply_upgrades_legacy_versions_and_preserves_finalized_patch_bytes(self) -> None:
        for version in ("1.0", "1.1", "1.2"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                work = self.work(Path(tmp), version=version)
                args = apply_args(work)
                # Noncanonical whitespace must survive copying; provenance hashes actual bytes.
                args.patch.write_text(json.dumps(make_patch(work), indent=2), encoding="utf-8")
                before = tree(args.current_dir)
                apply_revision(args)
                self.assertEqual(before, tree(args.current_dir))
                result = load_json(args.next_dir / "reconstruction-plan.json")
                self.assertEqual("1.2", result["schema_version"])
                self.assertEqual(2, result["page"]["iteration"])
                self.assertEqual(sha256_file(args.current_dir / "reconstruction-plan.json"), result["provenance"]["previous_plan_sha256"])
                self.assertEqual(sha256_file(args.patch), result["provenance"]["revision_patch_sha256"])
                self.assertEqual(args.patch.read_bytes(), (args.next_dir / "revision_patch.json").read_bytes())
                self.assertEqual([], load_json(args.next_dir / "plan-diff.json")["unauthorized_changes"])

    def test_chained_revision_preserves_previous_patch_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = self.work(Path(tmp))
            apply_revision(apply_args(work))
            fake_qa(work, 2)
            write_review(work, 2)
            args = apply_args(work, 2)
            # iteration 02/revision_patch.json is the applied input for the previous link.
            args.patch = args.current_dir / "next_revision_patch.json"
            atomic_write_json(args.patch, make_patch(work, 2, value=0.36))
            before = tree(args.current_dir)
            apply_revision(args)
            self.assertEqual(before, tree(args.current_dir))
            result = load_json(args.next_dir / "reconstruction-plan.json")
            self.assertEqual(3, result["page"]["iteration"])
            self.assertEqual(sha256_file(args.patch), result["provenance"]["revision_patch_sha256"])

    def test_cross_work_root_deterministic_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = self.work(Path(tmp) / "a")
            b = self.work(Path(tmp) / "b")
            self.assertEqual(tree(a), tree(b))
            apply_revision(apply_args(a))
            apply_revision(apply_args(b))
            self.assertEqual(tree(apply_args(a).next_dir), tree(apply_args(b).next_dir))

    def test_input_tampering_and_missing_inputs_never_publish(self) -> None:
        names = ["request.json", "source.png", "visual-spec.json", "reconstruction-handoff.json",
                 "iterations/01/reconstruction-plan.json", "iterations/01/review_report.json",
                 "iterations/01/review_evaluation.json", "iterations/01/qa_report.json", "iterations/01/layout.json"]
        for name in names:
            for missing in (False, True):
                with self.subTest(name=name, missing=missing), tempfile.TemporaryDirectory() as tmp:
                    work = self.work(Path(tmp))
                    path = work / name
                    if missing:
                        path.unlink()
                    elif name.endswith(".png"):
                        path.write_bytes(b"changed")
                    else:
                        doc = load_json(path)
                        if name.endswith("reconstruction-plan.json"):
                            doc["elements"][0]["content_ref"] = "wrong-authority"
                        elif name.endswith("review_evaluation.json"):
                            doc["inputs"]["review_report_sha256"] = "0" * 64
                        elif name.endswith("review_report.json"):
                            doc["review_context"]["layout_sha256"] = "0" * 64
                        else:
                            doc["schema_version"] = "invalid"
                        atomic_write_json(path, doc)
                    before = tree(apply_args(work).current_dir)
                    with self.assertRaises((AssetError, ContractError, ValueError)):
                        apply_revision(apply_args(work))
                    self.assertEqual(before, tree(apply_args(work).current_dir))
                    self.assertFalse(apply_args(work).next_dir.exists())

    def test_identity_hash_and_policy_failures(self) -> None:
        changes = [("task_id", "other"), ("page_id", "S02"), ("from_iteration", 2), ("to_iteration", 3),
                   ("base_plan_sha256", "0" * 64), ("based_on_review_sha256", "0" * 64), ("based_on_review_evaluation_sha256", "0" * 64)]
        for field, value in changes:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                work = self.work(Path(tmp))
                candidate = make_patch(work)
                candidate[field] = value
                atomic_write_json(apply_args(work).patch, candidate)
                with self.assertRaises((ContractError, AssetError)):
                    apply_revision(apply_args(work))
                self.assertFalse(apply_args(work).next_dir.exists())

    def test_review_identity_policy_and_baseline_provenance_are_enforced(self) -> None:
        for case in ("review-task", "review-iteration", "evaluation-task", "evaluation-iteration", "non-revise", "provenance"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                work = self.work(Path(tmp))
                args = apply_args(work)
                if case == "provenance":
                    path = args.current_dir / "reconstruction-plan.json"
                    doc = load_json(path)
                    doc["provenance"]["approved_design_sha256"] = "0" * 64
                else:
                    name = "review_report.json" if case.startswith("review-") else "review_evaluation.json"
                    path = args.current_dir / name
                    doc = load_json(path)
                    if case.endswith("task"):
                        doc["task_id"] = "different-task"
                    elif case.endswith("iteration"):
                        doc["iteration"] = 2
                    else:
                        doc["policy_decision"] = "pass"
                atomic_write_json(path, doc)
                atomic_write_json(args.patch, make_patch(work))
                with self.assertRaises((ContractError, AssetError)):
                    apply_revision(args)
                self.assertFalse(args.next_dir.exists())

    def test_atomicity_at_compile_validation_write_and_publish_boundaries(self) -> None:
        for point in ("revision_context.compile_reconstruction_plan", "revision_context.validate_documents",
                      "apply_revision_patch.atomic_write_bytes", "apply_revision_patch.atomic_write_json", "apply_revision_patch.os.rename"):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as tmp:
                work = self.work(Path(tmp))
                args = apply_args(work)
                before = tree(args.current_dir)
                with mock_patch(point, side_effect=RuntimeError("injected failure")), self.assertRaises(RuntimeError):
                    apply_revision(args)
                self.assertEqual(before, tree(args.current_dir))
                self.assertEqual(["01"], sorted(p.name for p in args.current_dir.parent.iterdir()))

    def test_existing_next_directory_is_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = self.work(Path(tmp))
            args = apply_args(work)
            args.next_dir.mkdir()
            (args.next_dir / "owned.txt").write_bytes(b"owned by user")
            before = tree(work)
            with self.assertRaises(AssetError):
                apply_revision(args)
            self.assertEqual(before, tree(work))

    def test_input_changes_during_staging_abort_publication(self) -> None:
        from asset_common import atomic_write_json as real_write
        for name in ("request.json", "source.png", "visual-spec.json", "reconstruction-handoff.json",
                     "iterations/01/revision_patch.json", "iterations/01/review_report.json", "iterations/01/review_evaluation.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                work = self.work(Path(tmp))
                def write_and_tamper(path, value):
                    real_write(path, value)
                    target = work / name
                    target.write_bytes(target.read_bytes() + b" ")
                with mock_patch("apply_revision_patch.atomic_write_json", side_effect=write_and_tamper), self.assertRaises(AssetError):
                    apply_revision(apply_args(work))
                self.assertEqual(["01"], sorted(p.name for p in (work / "iterations").iterdir()))

    def test_independent_diff_rejects_locked_top_level_and_reorder_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = self.work(Path(tmp))
            ctx = load_revision_context(work, apply_args(work).current_dir, SCHEMAS)
            candidate = make_patch(work)
            result, _, _ = validate_revision(ctx, candidate, sha256_file(apply_args(work).patch))
            for change in ("locked", "undeclared", "order", "top", "authority", "delete"):
                with self.subTest(change=change):
                    altered = copy.deepcopy(result)
                    if change == "locked":
                        altered["elements"][0]["style"]["font_size_pt"] = 31
                    elif change == "undeclared":
                        altered["elements"][2]["geometry"]["x"] = 0.46
                    elif change == "order":
                        altered["elements"].reverse()
                    elif change == "top":
                        altered["slide"]["background"] = "#000000"
                    elif change == "authority":
                        altered["elements"][2]["role"] = "other"
                    else:
                        altered["elements"].pop()
                    diff = plan_diff(ctx.documents["base"], altered, candidate, expected_provenance=result["provenance"])
                    self.assertTrue(diff["unauthorized_changes"])
                    with self.assertRaises(ContractError):
                        validate_plan_diff(ctx.documents["base"], altered, candidate, expected_provenance=result["provenance"])
                    with mock_patch("revision_context.apply_patch", return_value=(altered, {})), self.assertRaises(ContractError):
                        validate_revision(ctx, candidate, sha256_file(apply_args(work).patch))

    def test_raster_recrop_changes_pixel_crop_without_changing_stable_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = self.work(Path(tmp))
            write_review(work, target="hero")
            args = apply_args(work)
            atomic_write_json(args.patch, make_patch(work, target="hero", path="/asset_request/source_region/x", value=0.75))
            apply_revision(args)
            a, b = load_json(args.current_dir / "crops.json"), load_json(args.next_dir / "crops.json")
            self.assertEqual("hero", b["assets"][0]["id"])
            self.assertNotEqual(a["assets"][0]["box_px"], b["assets"][0]["box_px"])

    def test_allowed_geometry_z_order_optional_style_and_arrays(self) -> None:
        settings = [("card-02", "/geometry/x", 0.46), ("card-02", "/geometry/y", 0.39),
                    ("card-02", "/geometry/width", 0.24), ("card-02", "/geometry/height", 0.24),
                    ("card-02", "/z_index", 3), ("card-02", "/style/fill/transparency", 10),
                    ("title-object", "/style/underline", True), ("title-object", "/style/margin_in", [0.1, 0.1, 0.1, 0.1])]
        for target, path, value in settings:
            with self.subTest(path=path), tempfile.TemporaryDirectory() as tmp:
                work = self.work(Path(tmp))
                write_review(work, target=target)
                args = apply_args(work)
                atomic_write_json(args.patch, make_patch(work, target=target, path=path, value=value))
                apply_revision(args)
                change = load_json(args.next_dir / "plan-diff.json")["changed_elements"][0]["changes"][0]
                self.assertEqual(value, change["after"])
                self.assertTrue(change["after_exists"])

    def test_full_page_raster_is_rejected_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = self.work(Path(tmp))
            write_review(work, target="hero")
            candidate = make_patch(work, target="hero")
            candidate["operations"] = [{"issue_id": "issue-01", "element_id": "hero", "path": f"/{prefix}/{field}", "value": value}
                                        for prefix in ("geometry", "asset_request/source_region")
                                        for field, value in (("x", 0), ("y", 0), ("width", 1), ("height", 1))]
            atomic_write_json(apply_args(work).patch, candidate)
            with self.assertRaises(AssetError):
                apply_revision(apply_args(work))
            self.assertFalse(apply_args(work).next_dir.exists())

    def test_native_chart_table_revision_keeps_data_structure_and_native_types(self) -> None:
        for target, path, value in (("chart-01", "/geometry/x", 0.04), ("chart-01", "/style/color_tokens", ["#112233", "#445566"]),
                                    ("table-01", "/geometry/y", 0.31), ("table-01", "/style/column_width_ratios", [3, 1, 1])):
            with self.subTest(target=target, path=path), tempfile.TemporaryDirectory() as tmp:
                work = self.work(Path(tmp), native=True)
                write_review(work, target=target)
                args = apply_args(work)
                atomic_write_json(args.patch, make_patch(work, target=target, path=path, value=value))
                apply_revision(args)
                original = {e["id"]: e for e in load_json(args.current_dir / "layout.json")["elements"]}
                result = {e["id"]: e for e in load_json(args.next_dir / "layout.json")["elements"]}
                for element_id in ("chart-01", "table-01"):
                    for field in ("type", "data_ref", "categories", "series", "grid", "merges", "header_row_count", "header_bold", "header_fill"):
                        self.assertEqual(original[element_id].get(field), result[element_id].get(field), field)

    @unittest.skipUnless(os.environ.get("IVT_RUN_POWERPOINT_SMOKE") == "1", "set IVT_RUN_POWERPOINT_SMOKE=1 to run PowerPoint smoke")
    def test_powerpoint_canonical_revision_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = create_work(Path(tmp))
            baseline = pipeline(work)
            self.assertEqual(0, baseline.returncode, baseline.stdout + baseline.stderr)
            write_review(work)
            args = apply_args(work)
            from tests.runtime.test_p5_call_contract import P5CallContractTests
            calls = P5CallContractTests()
            call, manifest = calls.prepare(work)
            calls.respond(call, manifest, calls.response(work))
            finalized = calls.finalize(work, call)
            self.assertEqual(0, finalized.returncode, finalized.stdout + finalized.stderr)
            apply_revision(args)
            revised = pipeline(work, 2)
            self.assertEqual(0, revised.returncode, revised.stdout + revised.stderr)
            qa = load_json(args.next_dir / "qa_report.json")
            self.assertEqual("pass", qa["status"])
            self.assertEqual([], qa["hard_failures"])
            self.assertEqual("Microsoft PowerPoint", qa["rendering"]["renderer"])
            self.assertFalse(qa["rendering"]["fallback_used"])


if __name__ == "__main__":
    unittest.main()
