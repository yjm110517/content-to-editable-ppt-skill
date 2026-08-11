from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from schema_utils import ContractError, validate_schema


SCHEMA_DIR = ROOT / "content-to-editable-ppt" / "schemas"
H = "a" * 64
NOW = "2026-08-11T00:00:00Z"


def page() -> dict:
    return {
        "slide_id": "S01", "order": 1, "role": "cover", "purpose": "Introduce the topic",
        "key_message": "A clear opening", "title": {"content_ref": "S01-TITLE", "text": "P1 Content Planning"},
        "content_blocks": [{"content_ref": "S01-C01", "order": 1, "text": "Exact approved text", "source_refs": ["M01-F01"]}],
        "visual_intent": "hero title", "source_refs": ["M01-F01"],
    }


class P1ContractTests(unittest.TestCase):
    def test_all_p1_schema_documents_validate(self) -> None:
        documents = {
            "task_route": {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "task_id": "t", "route_id": "r1", "revision": 1, "parent_route_sha256": None, "route": "content_to_ppt", "intent_summary": "new deck", "evidence": ["explicit request"], "created_at_utc": NOW},
            "deck_request": {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "task_id": "t", "deck_id": "D03", "topic": "P1", "objective": "Explain P1", "audience": "developers", "language": "zh-CN", "page_count": 1, "output_ratio": "16:9", "source_material_ids": ["M01"], "must_preserve": [], "prohibited_changes": [], "visual_requirements": [], "external_research": "not_authorized"},
            "material_understanding": {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "materials-r1", "deck_id": "D03", "revision": 1, "parent_sha256": None, "external_research": "not_authorized", "status": "ready", "materials": [{"material_id": "M01", "display_name": "brief", "media_type": "text/plain", "read_status": "readable", "required_for_task": True, "blocking": False, "content_sha256": H, "reason": None}], "facts": [{"fact_id": "M01-F01", "text": "P1 freezes content", "kind": "fact", "source_refs": ["M01"]}], "warnings": [], "ignore_authorizations": [], "created_at_utc": NOW},
            "candidate_outline": {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "candidate-r1", "deck_id": "D03", "revision": 1, "parent_sha256": None, "material_understanding_sha256": H, "host_pass_counts": {"planning": 1, "revision": 0, "automatic_regeneration": 0}, "pages": [page()], "created_at_utc": NOW},
            "outline_confirmation": {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "confirmation_id": "confirm-1", "deck_id": "D03", "candidate_revision": 1, "candidate_sha256": H, "status": "confirmed", "user_message_sha256": H, "created_at_utc": NOW},
            "approved_outline": {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "approved-r1", "deck_id": "D03", "revision": 1, "parent_sha256": None, "candidate_revision": 1, "candidate_sha256": H, "confirmation_id": "confirm-1", "confirmation_sha256": H, "pages": [page()], "approved_at_utc": NOW},
            "approved_slide_content": {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "D03-S01-r1", "deck_id": "D03", "slide_id": "S01", "order": 1, "revision": 1, "parent_sha256": None, "approved_outline_revision": 1, "approved_outline_sha256": H, "confirmation_id": "confirm-1", "projection": {"tool_version": "1.0", "input_sha256": H, "output_content_sha256": H}, "title": page()["title"], "content_blocks": page()["content_blocks"], "status": "frozen", "frozen_at_utc": NOW},
        }
        for kind, document in documents.items():
            with self.subTest(kind=kind):
                validate_schema(kind, document, SCHEMA_DIR)

    def test_candidate_revision_two_requires_user_request_hash(self) -> None:
        document = {"schema_version": "1.0", "canonicalization_version": "p1-rfc8785-nfc-1", "artifact_id": "candidate-r2", "deck_id": "D03", "revision": 2, "parent_sha256": H, "material_understanding_sha256": H, "host_pass_counts": {"planning": 1, "revision": 1, "automatic_regeneration": 0}, "pages": [page()], "created_at_utc": NOW}
        with self.assertRaises(ContractError):
            validate_schema("candidate_outline", document, SCHEMA_DIR)


if __name__ == "__main__":
    unittest.main()
