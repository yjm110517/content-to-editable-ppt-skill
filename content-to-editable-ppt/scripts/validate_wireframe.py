from __future__ import annotations

import argparse
import json
from pathlib import Path

from schema_utils import ContractError, load_json
from wireframe_rules import candidate_manifest_digest, load_authority_bundle, validate_spec, validation_report


def write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate P2 Wireframe Specs against the P1 Authority Bundle")
    result.add_argument("--p1-state", type=Path, required=True)
    result.add_argument("--deck-request", type=Path, required=True)
    result.add_argument("--approved-outline", type=Path, required=True)
    result.add_argument("--slide-content-dir", type=Path, required=True)
    result.add_argument("--layout-requirements", type=Path, required=True)
    result.add_argument("--spec-dir", type=Path, required=True)
    result.add_argument("--report", type=Path, required=True)
    result.add_argument("--report-id", required=True)
    result.add_argument("--timestamp-utc")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        bundle = load_authority_bundle(
            p1_state_path=args.p1_state.resolve(), deck_request_path=args.deck_request.resolve(),
            approved_outline_path=args.approved_outline.resolve(), slide_content_dir=args.slide_content_dir.resolve(),
            layout_requirements_path=args.layout_requirements.resolve(),
        )
        specs = [load_json(path) for path in sorted(args.spec_dir.resolve().glob("*.json"))]
        issues = []
        expected_ids = set(bundle["pages"])
        actual_ids = {item.get("slide_id") for item in specs}
        if actual_ids != expected_ids:
            from wireframe_rules import BLOCKING, _issue
            _issue(issues, slide_id=None, classification=BLOCKING, code="spec_slide_set_mismatch", path="$.specs", message="Spec Slide IDs must exactly match Approved Outline")
        for spec in specs:
            slide_id = spec.get("slide_id")
            if slide_id not in bundle["pages"]:
                continue
            issues.extend(validate_spec(
                spec, approved_outline=bundle["approved_outline"], slide_content=bundle["slide_contents"][slide_id],
                page=bundle["pages"][slide_id], layout_requirements=bundle["layout_requirements"],
                output_ratio=bundle["deck_request"]["output_ratio"],
            ))
        report = validation_report(deck_id=bundle["deck_request"]["deck_id"], candidate_sha256=candidate_manifest_digest(specs), issues=issues, report_id=args.report_id, validated_at_utc=args.timestamp_utc)
        write_json(args.report.resolve(), report)
        print(json.dumps({"status": report["status"], "issues": len(issues)}, ensure_ascii=False))
        return {"pass": 0, "correctable": 2, "blocking": 4}[report["status"]]
    except ContractError as exc:
        print(json.dumps({"status": "blocking", "errors": exc.errors}, ensure_ascii=False))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
