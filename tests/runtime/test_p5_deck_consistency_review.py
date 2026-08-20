from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys_path = str(ROOT / "content-to-editable-ppt" / "scripts")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from deck_consistency_review import compile_consistency_report, prepare_deck_review_evidence  # noqa: E402
from schema_utils import ContractError  # noqa: E402


def _evidence() -> dict:
    return prepare_deck_review_evidence(
        deck_id="D03",
        contact_sheets={"approved": {"path": "a.png", "sha256": "1" * 64, "slides": 3}, "final": {"path": "b.png", "sha256": "2" * 64, "slides": 3}, "comparison": {"path": "c.png", "sha256": "3" * 64, "slides": 6}},
        visual_system_summary={"palette": ["#111111"], "typography": "Microsoft YaHei"},
        qa_report={"status": "pass", "blocking_issues": 0, "exception_pages": []},
        roundtrip_report={"status": "pass", "relationship_safety": "safe"},
        fidelity_inheritance={"p4_fidelity_inherited": True},
        exception_review_hashes=["4" * 64],
    )


def _pass_response() -> dict:
    return {
        "schema_version": "1.0",
        "artifact_type": "deck_consistency_reviewer_response",
        "deck_id": "D03",
        "reviewer_recommendation": "pass",
        "issues": [],
        "mandatory_checks": {
            "typography_consistent": True, "palette_consistent": True, "background_consistent": True,
            "card_language_consistent": True, "density_spacing_consistent": True, "visual_treatment_consistent": True,
            "navigation_consistent": True, "section_hierarchy_consistent": True, "same_deck_identity": True,
            "no_reopened_p4_fidelity": True,
        },
        "structured_upstream_revision": None,
    }


def _call_record() -> dict:
    return {
        "evidence_sha256": "a" * 64, "raw_response_sha256": "b" * 64, "finalized_response_sha256": "c" * 64,
        "role_config_sha256": "d" * 64, "prompt_sha256": "e" * 64, "response_schema_sha256": "f" * 64,
        "resolved_model_identity_sha256": "1" * 64, "transport_request_sha256": "2" * 64,
        "context_id": "ctx-live-001", "technical_retry_count": 0,
    }


class P5DeckConsistencyReviewTests(unittest.TestCase):
    def test_evidence_bundle_complete(self) -> None:
        evidence = _evidence()
        self.assertEqual(evidence["artifact_type"], "deck_consistency_review_evidence")
        self.assertTrue(evidence["reviewer_contract"]["must_not_reopen_p4_fidelity"])
        self.assertEqual(len(evidence["contact_sheets"]), 3)

    def test_fixture_replay_marked_not_satisfying_adr040(self) -> None:
        report = compile_consistency_report(deck_id="D03", evidence=_evidence(), reviewer_response=_pass_response(), call_record=None)
        self.assertEqual(report["reviewer_recommendation"], "pass")
        self.assertIsNone(report["call_record"])
        self.assertTrue(report["does_not_satisfy_adr_040"])

    def test_trusted_call_record_compiles(self) -> None:
        report = compile_consistency_report(deck_id="D03", evidence=_evidence(), reviewer_response=_pass_response(), call_record=_call_record())
        self.assertFalse(report["does_not_satisfy_adr_040"])
        self.assertEqual(report["call_record"]["context_id"], "ctx-live-001")

    def test_incomplete_call_record_rejected(self) -> None:
        record = _call_record()
        del record["response_schema_sha256"]
        with self.assertRaises(ContractError):
            compile_consistency_report(deck_id="D03", evidence=_evidence(), reviewer_response=_pass_response(), call_record=record)

    def test_reopened_p4_fidelity_rejected(self) -> None:
        response = _pass_response()
        response["mandatory_checks"]["no_reopened_p4_fidelity"] = False
        with self.assertRaises(ContractError) as context:
            compile_consistency_report(deck_id="D03", evidence=_evidence(), reviewer_response=response)
        self.assertEqual(context.exception.errors[0]["code"], "schema_error")

    def test_unknown_dimension_rejected(self) -> None:
        response = _pass_response()
        response["issues"] = [{"issue_id": "P5-ABC123DEF456", "severity": "major", "dimension": "page_level_fidelity", "slide_ids": ["S01"], "message": "bbox off"}]
        with self.assertRaises(ContractError):
            compile_consistency_report(deck_id="D03", evidence=_evidence(), reviewer_response=response)

    def test_upstream_revision_stage_mapping(self) -> None:
        response = _pass_response()
        response["reviewer_recommendation"] = "revise"
        response["issues"] = [{"issue_id": "P5-ABC123DEF456", "severity": "major", "dimension": "typography", "slide_ids": ["S02", "S03"], "message": "title font differs"}]
        response["mandatory_checks"]["typography_consistent"] = False
        response["structured_upstream_revision"] = [
            {"responsible_stage": "page reconstruction, editability, geometry", "issue_ids": ["P5-ABC123DEF456"], "affected_slide_ids": ["S02", "S03"], "reason_code": "reconstruction_fidelity_major", "required_revision_scope": "local_pages"}
        ]
        report = compile_consistency_report(deck_id="D03", evidence=_evidence(), reviewer_response=response, call_record=_call_record())
        self.assertEqual(report["structured_upstream_revision"][0]["responsible_stage"], "p4")
        self.assertEqual(report["structured_upstream_revision"][0]["required_revision_scope"], "local_pages")

    def test_production_cross_slide_outlier_compiles(self) -> None:
        response = _pass_response()
        response["schema_version"] = "1.1"
        response["reviewer_recommendation"] = "revise"
        response["issues"] = [{
            "issue_id": "P5-ABC123DEF456", "severity": "minor", "dimension": "typography", "slide_ids": ["S03"],
            "message": "S03 uses a different title hierarchy from the repeated S01/S02 pattern.",
            "finding_scope": "cross_slide_systemic",
            "cross_slide_basis": {"consistency_rule": "deck title hierarchy", "compared_slide_ids": ["S01", "S02", "S03"], "comparison_summary": "S01 and S02 establish the repeated hierarchy; S03 is the outlier.", "page_level_fidelity_reopened": False},
            "delivery_impact": {"artifact_change_required": True, "systemic_inconsistency": True, "accessibility_blocker": False},
        }]
        response["mandatory_checks"]["typography_consistent"] = False
        report = compile_consistency_report(deck_id="D03", evidence=_evidence(), reviewer_response=response, call_record=_call_record())
        self.assertEqual(report["issues"][0]["slide_ids"], ["S03"])

    def test_production_single_page_preference_without_comparison_rejected(self) -> None:
        response = _pass_response()
        response["schema_version"] = "1.1"
        response["issues"] = [{
            "issue_id": "P5-ABC123DEF456", "severity": "suggestion", "dimension": "density_spacing", "slide_ids": ["S03"],
            "message": "Move the title left.", "finding_scope": "cross_slide_systemic",
            "cross_slide_basis": {"consistency_rule": "single page preference", "compared_slide_ids": ["S01", "S02"], "comparison_summary": "No affected slide is included.", "page_level_fidelity_reopened": False},
            "delivery_impact": {"artifact_change_required": False, "systemic_inconsistency": False, "accessibility_blocker": False},
        }]
        with self.assertRaises(ContractError):
            compile_consistency_report(deck_id="D03", evidence=_evidence(), reviewer_response=response, call_record=_call_record())

    def test_unsafe_suggestion_rejected(self) -> None:
        response = _pass_response()
        response["schema_version"] = "1.1"
        response["issues"] = [{
            "issue_id": "P5-ABC123DEF456", "severity": "suggestion", "dimension": "palette", "slide_ids": ["S02"],
            "message": "Systemic palette drift.", "finding_scope": "cross_slide_systemic",
            "cross_slide_basis": {"consistency_rule": "deck palette", "compared_slide_ids": ["S01", "S02"], "comparison_summary": "S02 differs from S01.", "page_level_fidelity_reopened": False},
            "delivery_impact": {"artifact_change_required": False, "systemic_inconsistency": True, "accessibility_blocker": False},
        }]
        with self.assertRaises(ContractError):
            compile_consistency_report(deck_id="D03", evidence=_evidence(), reviewer_response=response, call_record=_call_record())

    def test_pass_with_failed_check_rejected(self) -> None:
        response = _pass_response()
        response["issues"] = [{"issue_id": "P5-ABC123DEF456", "severity": "minor", "dimension": "palette", "slide_ids": ["S01"], "message": "slight palette drift"}]
        response["mandatory_checks"]["palette_consistent"] = False
        with self.assertRaises(ContractError):
            compile_consistency_report(deck_id="D03", evidence=_evidence(), reviewer_response=response)


if __name__ == "__main__":
    unittest.main()
