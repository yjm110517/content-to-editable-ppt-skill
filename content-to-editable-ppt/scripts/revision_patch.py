from __future__ import annotations

import copy
from typing import Any

from schema_utils import ContractError, error


GEOMETRY_PATHS = {"/geometry/x", "/geometry/y", "/geometry/width", "/geometry/height"}
STYLE_PATHS = {
    "native_text": {"/style/font_face", "/style/font_size_pt", "/style/bold", "/style/italic", "/style/underline", "/style/transparency", "/style/color", "/style/align", "/style/valign", "/style/margin_in", "/style/fit", "/style/language"},
    "native_shape": {"/style/shape", "/style/fill/color", "/style/fill/transparency", "/style/line/color", "/style/line/transparency", "/style/line/width_pt", "/style/line/dash", "/style/line/begin_arrow", "/style/line/end_arrow", "/style/shadow/color", "/style/shadow/opacity", "/style/shadow/blur_pt", "/style/shadow/angle", "/style/shadow/offset_pt", "/style/radius_hint"},
    "native_connector": {"/style/line/color", "/style/line/transparency", "/style/line/width_pt", "/style/line/dash", "/style/line/begin_arrow", "/style/line/end_arrow"},
    "raster_asset": set(),
    "native_chart": {"/style/show_legend", "/style/show_value", "/style/number_format", "/style/color_tokens", "/style/font_face"},
    "native_table": {"/style/font_face", "/style/font_size_pt", "/style/color", "/style/header_fill", "/style/header_bold", "/style/body_fill", "/style/border_color", "/style/border_width_pt", "/style/align", "/style/valign", "/style/margin_in", "/style/number_format", "/style/column_width_ratios", "/style/row_height_ratios"},
}


def _index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if len({item["id"] for item in items}) != len(items):
        raise ContractError([error("$.id", "duplicate stable ID", "duplicate_id")])
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
    if not patch["operations"] or not patch["targets"] or not patch["revision_reason"].strip():
        _fail(failures, "$", "revision requires targets, operations and a reason", "revision_scope")
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
    if len(targets) != len(set(targets)) or len(linked) != len(set(linked)) or set(targets) & set(linked):
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
    relations = _index(handoff["semantic_structure"]["relations"])
    geometry_targets = {
        op["element_id"] for op in patch["operations"]
        if op["element_id"] in targets and op["element_id"] in elements
        and op["path"] in GEOMETRY_PATHS
        and _value_at(elements[op["element_id"]], op["path"]) != op["value"]
    }
    for item in patch["linked_elements"]:
        if not item["reason"].strip():
            _fail(failures, "$.linked_elements", "linked connector requires a concrete reason", "revision_scope")
        element = elements.get(item["element_id"])
        if element is None:
            _fail(failures, "$.linked_elements", "linked element is unknown", "unknown_linked_element")
        elif element["representation"] != "native_connector" or element["id"] not in authority_connectors or not ({element["from_id"], element["to_id"]} & geometry_targets):
            _fail(failures, "$.linked_elements", "linked element must be a directly connected Authority connector", "invalid_linked_element")
        else:
            relation = relations.get(authority_connectors[element["id"]], {})
            if any(element[key] != relation.get(key) for key in ("from_id", "to_id")):
                _fail(failures, "$.linked_elements", "linked endpoints differ from Authority", "topology_mismatch")
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
        if is_linked and not (
            set(issue_map.get(operation["issue_id"], {}).get("element_ids", []))
            & geometry_targets & {element.get("from_id"), element.get("to_id")}
        ):
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
    for operation in patch["operations"]:
        _set_at(elements[operation["element_id"]], operation["path"], operation["value"])
    result["schema_version"] = "1.2"
    result["page"]["iteration"] = patch["to_iteration"]
    result["provenance"] = {"reconstruction_handoff_sha256": handoff_sha256, "approved_design_sha256": approved_design_sha256, "previous_plan_sha256": patch["base_plan_sha256"], "revision_patch_sha256": patch_sha256}
    diff = validate_plan_diff(base_plan, result, patch, expected_provenance={
        "reconstruction_handoff_sha256": handoff_sha256,
        "approved_design_sha256": approved_design_sha256,
        "previous_plan_sha256": patch["base_plan_sha256"],
        "revision_patch_sha256": patch_sha256,
    })
    return result, diff


_MISSING = object()


def _diff_records(before: Any, after: Any, prefix: str = "") -> list[dict[str, Any]]:
    """Compare dictionaries recursively; arrays are indivisible contract fields."""
    if isinstance(before, dict) or isinstance(after, dict):
        if (isinstance(before, dict) or before is _MISSING) and (isinstance(after, dict) or after is _MISSING):
            left = before if isinstance(before, dict) else {}
            right = after if isinstance(after, dict) else {}
            if left or right:
                return [change for key in sorted(set(left) | set(right))
                        for change in _diff_records(left.get(key, _MISSING), right.get(key, _MISSING), f"{prefix}/{key}")]
    if before is not _MISSING and after is not _MISSING and before == after and type(before) is type(after):
        return []
    return [{"path": prefix or "/", "before_exists": before is not _MISSING,
             "after_exists": after is not _MISSING,
             "before": None if before is _MISSING else copy.deepcopy(before),
             "after": None if after is _MISSING else copy.deepcopy(after)}]


def plan_diff(base: dict[str, Any], result: dict[str, Any], patch: dict[str, Any], *, expected_provenance: dict[str, Any]) -> dict[str, Any]:
    before, after = _index(base["elements"]), _index(result["elements"])
    targets = set(patch["targets"])
    linked = {item["element_id"] for item in patch["linked_elements"]}
    operations = {(op["element_id"], op["path"]): op["value"] for op in patch["operations"]}
    changed, unchanged, unauthorized = [], [], []
    if list(before) != list(after):
        unauthorized.append({"element_id": None, "path": "/elements", "reason": "element membership or order changed"})
    for element_id in dict.fromkeys([*before, *after]):
        scope = "target" if element_id in targets else "linked" if element_id in linked else "locked"
        changes = _diff_records(before.get(element_id, _MISSING), after.get(element_id, _MISSING))
        if not changes:
            unchanged.append(element_id)
            continue
        changed.append({"element_id": element_id, "scope": scope, "paths": [c["path"] for c in changes], "changes": changes})
        allowed = allowed_paths(before[element_id], linked=scope == "linked") if element_id in before and scope != "locked" else set()
        for change in changes:
            key = (element_id, change["path"])
            if change["path"] not in allowed or key not in operations or not change["after_exists"] or change["after"] != operations[key]:
                unauthorized.append({"element_id": element_id, **change, "reason": "change is not an authorized field setting"})
    expected = copy.deepcopy({key: value for key, value in base.items() if key != "elements"})
    expected["schema_version"] = "1.2"
    expected["page"]["iteration"] = patch["to_iteration"]
    expected["provenance"] = expected_provenance
    actual = {key: value for key, value in result.items() if key != "elements"}
    for change in _diff_records(expected, actual):
        unauthorized.append({"element_id": None, **change, "reason": "unexpected non-element state"})
    for (element_id, path), value in operations.items():
        element = after.get(element_id, {})
        if _value_at(element, path) != value:
            unauthorized.append({"element_id": element_id, "path": path, "reason": "declared operation was not applied"})
    return {"schema_version": "1.0", "changed_elements": changed, "unchanged_elements": unchanged, "unauthorized_changes": unauthorized}


def validate_plan_diff(base: dict[str, Any], result: dict[str, Any], patch: dict[str, Any], *, expected_provenance: dict[str, Any]) -> dict[str, Any]:
    diff = plan_diff(base, result, patch, expected_provenance=expected_provenance)
    if diff["unauthorized_changes"]:
        raise ContractError([error(item["path"], item["reason"], "unauthorized_change") for item in diff["unauthorized_changes"]])
    return diff
