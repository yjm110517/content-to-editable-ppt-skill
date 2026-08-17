from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

from PIL import ImageFont

from canonical_artifact import canonical_sha256
from schema_utils import ContractError, error, validate_schema
from visual_system_authority import SCHEMA_DIR


DATA_HEADER = "CONTENT DATA — SEMANTIC CONTEXT ONLY\nDO NOT RENDER THESE STRINGS INTO THE GENERATED VISUAL LAYER"
NEGATIVE_PROMPT = "No readable text, letters, numbers, labels, logos, watermarks, external assets, extra facts, redrawn resolved icons, or flattened text-bearing slide screenshots."


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def resolve_font_file(family: str, fallback: str) -> tuple[str, Path]:
    aliases = {
        "microsoft yahei": "msyh.ttc", "微软雅黑": "msyh.ttc", "arial": "arial.ttf",
        "calibri": "calibri.ttf", "aptos": "aptos.ttf", "simsun": "simsun.ttc", "宋体": "simsun.ttc",
    }
    root = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in (family, fallback):
        direct = root / aliases.get(name.casefold(), "")
        if direct.is_file():
            return name, direct
    raise ContractError([error("$.hard_constraints.typography", f"font file unavailable: {family} / {fallback}", "font_environment_unavailable")])


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*|\s+|.", text, re.DOTALL)


def _line_count(text: str, font: ImageFont.FreeTypeFont, width_px: int) -> int:
    lines = 1; used = 0.0
    for token in _tokens(text):
        if token == "\n": lines += 1; used = 0; continue
        amount = font.getlength(token)
        if used and used + amount > width_px:
            lines += 1; used = 0
        if amount > width_px:
            for char in token:
                char_width = font.getlength(char)
                if used and used + char_width > width_px: lines += 1; used = 0
                used += char_width
        else: used += amount
    return lines


def compile_text_footprints(visual_system: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    validate_schema("deck_visual_system", visual_system, SCHEMA_DIR)
    canvas = visual_system["hard_constraints"]["canvas"]
    files: dict[str, tuple[str, Path]] = {}
    for token, policy in visual_system["hard_constraints"]["typography"].items():
        files[token] = resolve_font_file(policy["family"], policy["fallback_family"])
    font_env = canonical_sha256({key: {"family": value[0], "sha256": _sha(value[1].read_bytes())} for key, value in sorted(files.items())})
    entries = []
    for content in sorted(bundle["slide_contents"].values(), key=lambda item: item["order"]):
        items = [(content["title"], "title", "title"), *[(item, "body", "body") for item in sorted(content["content_blocks"], key=lambda item: item["order"])]]
        for item, role, token in items:
            text = _normalize(item["text"]); policy = visual_system["hard_constraints"]["typography"][token]
            family, font_path = files[token]; font_px = max(1, round(policy["size_pt"] * 4 / 3)); font = ImageFont.truetype(str(font_path), font_px)
            low, high = max(1, canvas["width_px"] // 5), canvas["width_px"] * 9 // 10
            if _line_count(text, font, high) > policy["max_lines"]:
                raise ContractError([error(f"$.slide_contents.{content['slide_id']}.{item['content_ref']}", "text cannot fit within maximum width and line budget", "text_footprint_blocking")])
            while low < high:
                middle = (low + high) // 2
                if _line_count(text, font, middle) <= policy["max_lines"]: high = middle
                else: low = middle + 1
            lines = _line_count(text, font, low); padding = 250
            line_px = math.ceil(font_px * policy["line_height_milli"] / 1000)
            entries.append({"slide_id":content["slide_id"],"content_ref":item["content_ref"],"role":role,"text_sha256":_sha(text.encode("utf-8")),"font_token":token,"font_family":family,"font_file_sha256":_sha(font_path.read_bytes()),"font_size_pt":policy["size_pt"],"line_height_milli":policy["line_height_milli"],"estimated_lines":lines,"max_lines":policy["max_lines"],"preferred_width":math.ceil(low*10000/canvas["width_px"]),"min_height":min(10000,math.ceil(line_px*lines*10000/canvas["height_px"])+padding*2),"safe_padding":padding})
    result={"schema_version":"1.0","artifact_type":"text_footprint_manifest","deck_id":bundle["deck_id"],"deck_visual_system_sha256":canonical_sha256(visual_system),"slide_content_manifest_sha256":bundle["hashes"]["slide_content_manifest_sha256"],"algorithm":"pillow-10.4-96dpi-v1","font_environment_sha256":font_env,"entries":entries,"status":"pass"}
    validate_schema("text_footprint_manifest",result,SCHEMA_DIR); return result


def _escape(value: str) -> str:
    return _normalize(value).replace("<<<", "‹‹‹").replace(">>>", "›››")


def _anchor(bundle: dict[str, Any], system: dict[str, Any]) -> tuple[str, list[str]]:
    family_by_role={item["slide_role"]:item["family"] for item in system["soft_design_guidance"]["template_families"]}
    pages={item["slide_id"]:item for item in bundle["approved_outline"]["pages"]}; slides=bundle["p2_manifest"]["slides"]
    frequencies={family:sum(1 for page in pages.values() if family_by_role[page["role"]]==family) for family in set(family_by_role.values())}
    special={"cover","closing","section","section divider","opening"}; scored=[]; high=[]
    index={item["visual_ref"]:item for item in bundle["icon_asset_index"]["entries"]}
    for slide in slides:
        page=pages[slide["slide_id"]]; visuals=slide["visual_placeholders"]; family=family_by_role[page["role"]]
        raster=sum(1 for item in visuals if item["role"]=="icon" and index[item["visual_ref"]]["status"]=="raster_handoff_pending")
        exceptional=any(item["role"]=="diagram" and item["subtype"]=="architecture" for item in visuals) or len(visuals)>=4
        if raster or exceptional or len(page["content_blocks"])>=5: high.append(slide["slide_id"])
        eligible=int(page["role"].casefold() not in special); core=int(bool(page["content_blocks"]))+int(bool(visuals))+int(any(item["role"] in {"icon","image"} for item in visuals)); moderate=int(1<=len(visuals)<=3)
        scored.append(((eligible,frequencies[family],-int(exceptional or raster>0),core,moderate,-slide["order"]),slide["slide_id"]))
    scored.sort(reverse=True); return scored[0][1],sorted(high,key=lambda value:pages[value]["order"])


def _intents(slide: dict[str, Any], footprint: dict[str, Any], icon_index: dict[str, Any]) -> list[dict[str, Any]]:
    entries={(item["slide_id"],item["content_ref"]):item for item in footprint["entries"]}; icons={item["visual_ref"]:item for item in icon_index["entries"]}; result=[]
    for ref in slide["content_refs"]:
        result.append({"source_ref":ref,"element_owner":"deterministic_compositor","render_policy":"formal_text_overlay","footprint_ref":f"{slide['slide_id']}:{ref}","future_element_map_id":f"EL-{ref}"})
    for visual in slide["visual_placeholders"]:
        if visual["role"]=="icon" and icons[visual["visual_ref"]]["status"]=="resolved_svg": owner,policy="deterministic_compositor","resolved_svg_overlay"
        elif visual["role"]=="icon": owner,policy="generated_visual_layer","generated_extraction_candidate"
        elif visual["role"]=="chart": owner,policy="deterministic_compositor","chart_preview_overlay"
        elif visual["role"]=="image": owner,policy="generated_visual_layer","generated_image"
        elif visual["role"]=="illustration": owner,policy="generated_visual_layer","generated_illustration"
        else: owner,policy="generated_visual_layer","generated_diagram_structure"
        result.append({"source_ref":visual["visual_ref"],"element_owner":owner,"render_policy":policy,"footprint_ref":None,"future_element_map_id":f"EL-{visual['visual_ref']}"})
    return result


def compile_prompt_package(system: dict[str, Any], footprint: dict[str, Any], bundle: dict[str, Any], previous: dict[str, Any] | None=None) -> tuple[dict[str, Any],dict[str, Any]]:
    validate_schema("deck_visual_system",system,SCHEMA_DIR); validate_schema("text_footprint_manifest",footprint,SCHEMA_DIR)
    anchor,high=_anchor(bundle,system); pages={item["slide_id"]:item for item in bundle["approved_outline"]["pages"]}; candidates={item["slide_id"]:item for item in bundle["p2_candidate"]["slides"]}; contents=bundle["slide_contents"]; families={item["slide_role"]:item["family"] for item in system["soft_design_guidance"]["template_families"]}; old={item["slide_id"]:item for item in (previous or {}).get("slides",[])}
    shared="HARD VISUAL CONSTRAINTS\n"+json.dumps(system["hard_constraints"],ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\nSOFT DESIGN GUIDANCE — recommendations, not fixed layout\n"+json.dumps(system["soft_design_guidance"],ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\nGenerated Visual Layer is not the Final or Approved Design Preview. Preserve freedom for asymmetry, scale contrast, overlap, and irregular rhythm while respecting hard constraints."
    slides=[]
    for slide in sorted(bundle["p2_manifest"]["slides"],key=lambda item:item["order"]):
        sid=slide["slide_id"]; page=pages[sid]; content=contents[sid]; cand=candidates[sid]; intents=_intents(slide,footprint,bundle["icon_asset_index"]); relevant=[item for item in footprint["entries"] if item["slide_id"]==sid]
        data={"slide_id":sid,"role":page["role"],"purpose":page["purpose"],"key_message":page["key_message"],"content":{"title":content["title"],"blocks":content["content_blocks"]},"layout_draft":cand["layout_draft"],"layout_notes":cand["layout_notes"],"visual_placeholders":slide["visual_placeholders"],"text_footprints":relevant,"element_intents":intents}
        input_sha=canonical_sha256({"system":canonical_sha256(system),"slide":data,"icon_index":bundle["hashes"]["p3_icon_asset_index_sha256"]}); reused=sid in old and old[sid]["prompt_input_sha256"]==input_sha
        prompt=old[sid]["prompt"] if reused else shared+"\n\n"+DATA_HEADER+"\n<<<BEGIN_SLIDE_DATA>>>\n"+_escape(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":")))+"\n<<<END_SLIDE_DATA>>>\n\nReserve every Text Footprint as minimum clear space. Do not draw compositor-owned elements. Raster extraction candidates must be isolated, unoccluded, text-free, with minimum_short_edge=800 and safe_padding=300."
        slides.append({"slide_id":sid,"order":slide["order"],"role":page["role"],"template_family":families[page["role"]],"prompt_input_sha256":input_sha,"prompt_sha256":_sha(prompt.encode("utf-8")),"prompt":prompt,"element_intents":intents,"reused":reused})
    package={"schema_version":"1.0","artifact_type":"deck_prompt_package","deck_id":bundle["deck_id"],"deck_visual_system_sha256":canonical_sha256(system),"text_footprint_manifest_sha256":canonical_sha256(footprint),**bundle["hashes"],"generation_policy":{"provider_policy":"runtime_default","model_policy":"runtime_default","initial_generation_limit":1,"technical_retry_limit":2},"shared_prompt":shared,"negative_prompt":NEGATIVE_PROMPT,"style_anchor_slide_id":anchor,"high_risk_slide_ids":high,"slides":slides,"status":"compiled"}
    validate_schema("deck_prompt_package",package,SCHEMA_DIR)
    anchor_slide=next(item for item in slides if item["slide_id"]==anchor); request={"schema_version":"1.0","artifact_type":"style_anchor_request","deck_id":bundle["deck_id"],"deck_prompt_package_sha256":canonical_sha256(package),"deck_visual_system_sha256":canonical_sha256(system),"slide_id":anchor,"slide_prompt_sha256":anchor_slide["prompt_sha256"],"selection_basis":"representativeness_first_v1","high_risk_slide_ids":high,"status":"ready_for_generation"}; validate_schema("style_anchor_request",request,SCHEMA_DIR); return package,request


def apply_correction(candidate:dict[str,Any],report:dict[str,Any],correction:dict[str,Any])->dict[str,Any]:
    validate_schema("deck_visual_system_correction_record",correction,SCHEMA_DIR)
    if correction["candidate_sha256"]!=canonical_sha256(candidate) or correction["validation_report_sha256"]!=canonical_sha256(report): raise ContractError([error("$","Correction does not bind current Candidate and Report","stale_correction")])
    issues={item["issue_id"]:item for item in report["issues"] if item["correctable"]}; result=copy.deepcopy(candidate)
    for op in correction["operations"]:
        issue=issues.get(op["validation_issue_id"])
        if issue is None or not op["path"].startswith(issue["path"].replace("$.","/").replace(".","/")): raise ContractError([error(op["path"],"Correction is not bound to the reported issue","correction_not_allowed")])
        parts=[part for part in op["path"].split("/") if part]; target=result
        for part in parts[:-1]: target=target[int(part)] if isinstance(target,list) else target[part]
        key=int(parts[-1]) if isinstance(target,list) else parts[-1]; current=target[key] if op["op"]!="add" else None
        if current!=op["before"]: raise ContractError([error(op["path"],"Correction before value mismatch","stale_correction")])
        if op["op"]=="remove": del target[key]
        elif op["op"]=="add": target.insert(key,op["after"]) if isinstance(target,list) else target.__setitem__(key,op["after"])
        else: target[key]=op["after"]
    validate_schema("deck_visual_system_candidate",result,SCHEMA_DIR); return result
