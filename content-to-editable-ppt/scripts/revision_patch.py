from __future__ import annotations

import copy
from typing import Any

from schema_utils import ContractError, error, validate_schema, validate_semantics


GEOMETRY_PATHS = {"/geometry/x", "/geometry/y", "/geometry/width", "/geometry/height"}
STYLE_PATHS = {
    "native_text": {"/style/font_face", "/style/font_size_pt", "/style/bold", "/style/italic", "/style/color", "/style/align", "/style/valign", "/style/margin_in", "/style/fit", "/style/language"},
    "native_shape": {"/style/shape", "/style/fill/color", "/style/fill/transparency", "/style/line/color", "/style/line/transparency", "/style/line/width_pt", "/style/line/dash", "/style/line/begin_arrow", "/style/line/end_arrow", "/style/shadow/color", "/style/shadow/opacity", "/style/shadow/blur_pt", "/style/shadow/angle", "/style/shadow/offset_pt", "/style/radius_hint"},
    "native_connector": {"/style/line/color", "/style/line/transparency", "/style/line/width_pt", "/style/line/dash", "/style/line/begin_arrow", "/style/line/end_arrow"},
    "raster_asset": set(),
    "native_chart": {"/style/show_legend", "/style/show_value", "/style/number_format", "/style/color_tokens", "/style/font_face"},
    "native_table": {"/style/font_face", "/style/font_size_pt", "/style/color", "/style/header_fill", "/style/header_bold", "/style/body_fill", "/style/border_color", "/style/border_width_pt", "/style/align", "/style/valign", "/style/margin_in", "/style/number_format", "/style/column_width_ratios", "/style/row_height_ratios"},
}


def _index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in items}


def _value_at(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.strip("/").split("/"):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_at(value: dict[str, Any], path: str, replacement: Any) -> None:
    current: dict[str, Any] = value
    parts = path.strip("/").split("/")
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        child = current[part]
        if not isinstance(child, dict):
            raise ValueError(path)
        current = child
    current[parts[-1]] = copy.deepcopy(replacement)


def allowed_paths(element: dict[str, Any], *, linked: bool) -> set[str]:
    paths = set(GEOMETRY_PATHS)
    if linked:
        return paths if element["representation"] == "native_connector" else set()
    paths.add("/z_index")
    paths.update(STYLE_PATHS.get(element["representation"], set()))
    if element["representation"] == "raster_asset":
        paths.update({f"/asset_request/source_region/{field}" for field in ("x", "y", "width", "height")})
    return paths


def _fail(failures: list[dict[str, str]], path: str, message: str, code: str) -> None:
    failures.append(error(path, message, code))


def validate_patch(
    patch: dict[str, Any], base_plan: dict[str, Any], handoff: dict[str, Any], review: dict[str, Any], evaluation: dict[str, Any],
    *, task_id: str, base_sha256: str, review_sha256: str, evaluation_sha256: str,
) -> None:
    failures: list[dict[str, str]] = []
    elements = _index(base_plan["elements"])
    targets = list(patch["targets"])
    linked = [item["element_id"] for item in patch["linked_elements"]]
    issue_map = _index(review["issues"])
    approved = set(review["approved_elements"])
    if patch["task_id"] != task_id or patch["page_id"] != base_plan["page"]["id"]:
        _fail(failures, "$", "patch task or page does not match the baseline", "identity_mismatch")
    if patch["from_iteration"] != base_plan["page"]["iteration"] or patch["to_iteration"] != patch["from_iteration"] + 1:
        _fail(failures, "$.to_iteration", "revision iterations must be consecutive from the baseline", "iteration_mismatch")
    for name, actual, expected in (("base_plan_sha256", patch["base_plan_sha256"], base_sha256), ("based_on_review_sha256", patch["based_on_review_sha256"], review_sha256), ("based_on_review_evaluation_sha256", patch["based_on_review_evaluation_sha256"], evaluation_sha256)):
        if actual != expected:
            _fail(failures, f"$.{name}", "revision input hash is stale", "hash_conflict")
    if evaluation["policy_decision"] != "revise":
        _fail(failures, "$.based_on_review_evaluation_sha256", "revision requires a revise policy decision", "policy_conflict")
    if len(linked) != len(set(linked)) or set(targets) & set(linked):
        _fail(failures, "$.linked_elements", "targets and linked elements must be unique and disjoint", "revision_scope")
    for target in targets:
        if target not in elements:
            _fail(failures, "$.targets", f"unknown target: {target}", "unknown_target")
        elif target in approved:
            _fail(failures, "$.targets", f"approved element cannot be targeted: {target}", "approved_element")
    authority_connectors = {
        item["id"]: item["relation_ref"]
        for item in handoff["semantic_structure"]["objects"]
        if item["kind"] == "connector"
    }
    for item in patch["linked_elements"]:
        element = elements.get(item["element_id"])
        if element is None:
            _fail(failures, "$.linked_elements", "linked element is unknown", "unknown_linked_element")
        elif element["representation"] != "native_connector" or element["id"] not in authority_connectors or not ({element["from_id"], element["to_id"]} & set(targets)):
            _fail(failures, "$.linked_elements", "linked element must be a directly connected Authority connector", "invalid_linked_element")
    seen: set[tuple[str, str]] = set()
    changed: set[str] = set()
    for index, operation in enumerate(patch["operations"]):
        path = f"$.operations[{index}]"
        element = elements.get(operation["element_id"])
        if element is None:
            _fail(failures, path + ".element_id", "operation targets an unknown element", "unknown_target")
            continue
        is_linked = operation["element_id"] in linked
        if operation["element_id"] not in targets and not is_linked:
            _fail(failures, path + ".element_id", "operation modifies an implicitly locked element", "locked_element")
        if operation["issue_id"] not in issue_map:
            _fail(failures, path + ".issue_id", "operation references an unknown issue", "unknown_issue")
        else:
            issue = issue_map[operation["issue_id"]]
            if issue["recoverability"] != "recoverable" or issue["severity"] == "suggestion" or (not is_linked and operation["element_id"] not in issue["element_ids"]):
                _fail(failures, path + ".issue_id", "operation must reference a recoverable issue for its element", "issue_scope")
        if is_linked and not any(operation["issue_id"] in issue_map and set(issue_map[operation["issue_id"]]["element_ids"]) & set(targets) for _ in [0]):
            _fail(failures, path + ".issue_id", "linked connector operation must reference a target issue", "issue_scope")
        if operation["path"] not in allowed_paths(element, linked=is_linked):
            _fail(failures, path + ".path", "operation path is not allowed for this revision scope", "forbidden_path")
        key = (operation["element_id"], operation["path"])
        if key in seen:
            _fail(failures, path, "duplicate element/path operation", "duplicate_operation")
        seen.add(key)
        if _value_at(element, operation["path"]) == operation["value"]:
            _fail(failures, path, "operation does not change the baseline", "no_op")
        changed.add(operation["element_id"])
    for target in targets:
        if target not in changed:
            _fail(failures, "$.targets", "each target must have an operation", "missing_target_operation")
    for item in patch["linked_elements"]:
        if item["element_id"] not in changed:
            _fail(failures, "$.linked_elements", "each linked element must have an operation", "missing_linked_operation")
    if failures:
        raise ContractError(failures)


def apply_patch(base_plan: dict[str, Any], patch: dict[str, Any], *, handoff_sha256: str, approved_design_sha256: str, patch_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    result = copy.deepcopy(base_plan)
    elements = _index(result["elements"])
    before = _index(base_plan["elements"])
    linked = {item["element_id"] for item in patch["linked_elements"]}
    for operation in patch["operations"]:
        _set_at(elements[operation["element_id"]], operation["path"], operation["value"])
    result["schema_version"] = "1.2"
    result["page"]["iteration"] = patch["to_iteration"]
    result["provenance"] = {"reconstruction_handoff_sha256": handoff_sha256, "approved_design_sha256": approved_design_sha256, "previous_plan_sha256": patch["base_plan_sha256"], "revision_patch_sha256": patch_sha256}
    changed, unchanged = [], []
    for element in result["elements"]:
        old = before[element["id"]]
        if old == element:
            unchanged.append(element["id"])
            continue
        changed.append({"element_id": element["id"], "scope": "linked" if element["id"] in linked else "target", "paths": _diff_paths(old, element)})
    return result, {"schema_version": "1.0", "changed_elements": changed, "unchanged_elements": unchanged, "unauthorized_changes": []}


def _diff_paths(before: Any, after: Any, prefix: str = "") -> list[str]:
    if type(before) is not type(after) or not isinstance(before, dict):
        return [] if before == after else [prefix or "/"]
    result: list[str] = []
    for key in sorted(set(before) | set(after)):
        path = f"{prefix}/{key}"
        if key not in before or key not in after:
            result.append(path)
        else:
            result.extend(_diff_paths(before[key], after[key], path))
    return result
