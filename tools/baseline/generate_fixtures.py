from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1672
HEIGHT = 941
RATIO = "16:9"
CASES = ("B01", "B02", "B03", "B04", "B05", "B06")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_dir = Path("C:/Windows/Fonts")
    candidates = [
        font_dir / ("msyhbd.ttc" if bold else "msyh.ttc"),
        font_dir / ("arialbd.ttf" if bold else "arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    raise RuntimeError("Microsoft YaHei or Arial is required to generate P0 fixtures")


def canvas(accent: tuple[int, int, int] = (35, 104, 220)) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        t = y / max(1, HEIGHT - 1)
        color = tuple(round(250 - t * (250 - channel) * 0.07) for channel in accent)
        draw.line((0, y, WIDTH, y), fill=color)
    draw.ellipse((1350, -220, 1850, 280), fill=(235, 244, 255))
    draw.ellipse((-180, 720, 420, 1180), fill=(242, 247, 255))
    return image, draw


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 24,
            fill: tuple[int, int, int] = (255, 255, 255), outline: tuple[int, int, int] = (186, 211, 248), width: int = 3) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int,
          color: tuple[int, int, int] = (20, 52, 112), bold: bool = False,
          anchor: str | None = None) -> None:
    draw.text(xy, text, font=font(size, bold), fill=color, anchor=anchor)


def arrow(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: tuple[int, int, int] = (64, 128, 232), width: int = 8) -> None:
    draw.line(points, fill=color, width=width, joint="curve")
    x1, y1 = points[-2]
    x2, y2 = points[-1]
    dx, dy = x2 - x1, y2 - y1
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    tip = (x2, y2)
    left = (round(x2 - ux * 24 + px * 13), round(y2 - uy * 24 + py * 13))
    right = (round(x2 - ux * 24 - px * 13), round(y2 - uy * 24 - py * 13))
    draw.polygon((tip, left, right), fill=color)


def icon_badge(draw: ImageDraw.ImageDraw, center: tuple[int, int], kind: str) -> None:
    x, y = center
    draw.rounded_rectangle((x - 55, y - 55, x + 55, y + 55), radius=22, fill=(226, 239, 255), outline=(150, 194, 250), width=2)
    blue = (25, 103, 225)
    if kind == "target":
        for r in (34, 23, 11):
            draw.ellipse((x - r, y - r, x + r, y + r), outline=blue, width=6)
        arrow(draw, [(x + 4, y - 4), (x + 35, y - 35)], blue, 5)
    elif kind == "bars":
        for index, height in enumerate((28, 45, 66)):
            left = x - 36 + index * 28
            draw.rounded_rectangle((left, y + 35 - height, left + 17, y + 35), radius=4, fill=blue)
    elif kind == "check":
        draw.rounded_rectangle((x - 29, y - 38, x + 29, y + 38), radius=7, outline=blue, width=6)
        draw.line((x - 17, y + 2, x - 4, y + 16, x + 20, y - 14), fill=blue, width=7, joint="curve")
    elif kind == "spark":
        draw.polygon(((x, y - 40), (x + 11, y - 10), (x + 41, y), (x + 11, y + 10), (x, y + 40), (x - 11, y + 10), (x - 41, y), (x - 11, y - 10)), fill=blue)
    elif kind == "people":
        for dx in (-24, 0, 24):
            draw.ellipse((x + dx - 11, y - 32, x + dx + 11, y - 10), fill=blue)
            draw.rounded_rectangle((x + dx - 16, y - 4, x + dx + 16, y + 31), radius=10, fill=blue)
    else:
        draw.ellipse((x - 31, y - 31, x + 31, y + 31), outline=blue, width=7)
        draw.line((x - 20, y + 8, x - 5, y + 23, x + 25, y - 20), fill=blue, width=7)


def draw_b01(path: Path) -> list[tuple[str, str]]:
    image, draw = canvas((42, 113, 210))
    label(draw, (86, 76), "项目启动简报", 58, bold=True)
    label(draw, (88, 150), "从目标到行动的三步协作框架", 27, color=(72, 98, 142))
    colors = [(231, 241, 255), (235, 248, 244), (255, 243, 224)]
    titles = ["01  明确目标", "02  分配行动", "03  验证结果"]
    bodies = ["统一范围与成功标准", "确认负责人和完成时间", "用证据复盘并持续改进"]
    for index, (title, body) in enumerate(zip(titles, bodies)):
        x1 = 90 + index * 520
        rounded(draw, (x1, 270, x1 + 445, 635), 30, colors[index], (158, 190, 232), 3)
        draw.ellipse((x1 + 36, 312, x1 + 112, 388), fill=(37, 105, 222))
        label(draw, (x1 + 74, 350), str(index + 1), 34, color=(255, 255, 255), bold=True, anchor="mm")
        label(draw, (x1 + 42, 420), title, 34, bold=True)
        label(draw, (x1 + 42, 492), body, 23, color=(58, 77, 110))
        draw.line((x1 + 42, 560, x1 + 365, 560), fill=(155, 181, 220), width=3)
    rounded(draw, (328, 744, 1344, 838), 40, (31, 101, 218), (31, 101, 218), 1)
    label(draw, (836, 791), "目标清晰 · 行动可追踪 · 结果可验证", 31, color=(255, 255, 255), bold=True, anchor="mm")
    image.save(path, format="PNG", compress_level=9)
    return [("title", "项目启动简报"), ("subtitle", "从目标到行动的三步协作框架"),
            ("step-1", "01  明确目标"), ("body-1", "统一范围与成功标准"),
            ("step-2", "02  分配行动"), ("body-2", "确认负责人和完成时间"),
            ("step-3", "03  验证结果"), ("body-3", "用证据复盘并持续改进"),
            ("footer", "目标清晰 · 行动可追踪 · 结果可验证")]


def draw_b02(path: Path) -> list[tuple[str, str]]:
    image, draw = canvas((30, 112, 230))
    label(draw, (82, 64), "团队能力地图", 57, bold=True)
    label(draw, (84, 139), "六个能力模块共同支撑稳定交付", 26, color=(76, 103, 151))
    data = [
        ("目标管理", "把方向转化为可衡量结果", "target"),
        ("数据洞察", "用证据发现关键变化", "bars"),
        ("质量保障", "在交付前发现结构问题", "check"),
        ("创新实验", "用小步试验降低不确定性", "spark"),
        ("协同共创", "让角色边界和交接清晰", "people"),
        ("持续改进", "让每次复盘产生新行动", "done"),
    ]
    for index, (title, body, kind) in enumerate(data):
        row, col = divmod(index, 3)
        x1, y1 = 75 + col * 525, 230 + row * 285
        rounded(draw, (x1, y1, x1 + 470, y1 + 225), 28, (255, 255, 255), (174, 205, 247), 3)
        icon_badge(draw, (x1 + 85, y1 + 92), kind)
        label(draw, (x1 + 165, y1 + 58), title, 30, bold=True)
        label(draw, (x1 + 165, y1 + 117), body, 20, color=(73, 92, 126))
        draw.line((x1 + 165, y1 + 165, x1 + 410, y1 + 165), fill=(200, 219, 244), width=3)
    image.save(path, format="PNG", compress_level=9)
    items = [("title", "团队能力地图"), ("subtitle", "六个能力模块共同支撑稳定交付")]
    for index, (title, body, _) in enumerate(data, start=1):
        items.extend(((f"card-{index}-title", title), (f"card-{index}-body", body)))
    return items


def draw_b03(path: Path) -> list[tuple[str, str]]:
    image, draw = canvas((24, 128, 169))
    label(draw, (82, 66), "城市微更新观察", 57, bold=True)
    label(draw, (84, 143), "在有限空间里创造更友好的公共体验", 26, color=(62, 100, 119))
    photo = Image.new("RGB", (870, 565), (190, 224, 238))
    pd = ImageDraw.Draw(photo)
    for y in range(565):
        t = y / 564
        pd.line((0, y, 870, y), fill=(round(174 + 55 * t), round(218 + 25 * t), round(239 - 18 * t)))
    pd.ellipse((90, 65, 220, 195), fill=(255, 201, 65))
    pd.polygon(((0, 420), (235, 230), (440, 420)), fill=(82, 145, 133))
    pd.polygon(((230, 430), (535, 190), (870, 430)), fill=(49, 113, 120))
    pd.rectangle((0, 410, 870, 565), fill=(92, 143, 103))
    pd.rounded_rectangle((560, 295, 735, 520), radius=18, fill=(246, 238, 220), outline=(79, 96, 104), width=5)
    pd.rectangle((590, 340, 630, 520), fill=(72, 111, 134))
    pd.rectangle((658, 330, 700, 520), fill=(72, 111, 134))
    pd.ellipse((620, 245, 675, 300), fill=(228, 89, 62))
    image.paste(photo, (90, 245))
    draw.rounded_rectangle((90, 245, 960, 810), radius=28, outline=(255, 255, 255), width=9)
    rounded(draw, (1040, 245, 1575, 810), 30, (255, 255, 255), (171, 214, 225), 3)
    label(draw, (1090, 305), "观察结论", 35, bold=True, color=(13, 102, 127))
    bullets = ["增加可停留的遮阴空间", "保留清晰的步行通道", "用色彩建立区域识别", "让设施支持多种活动"]
    for index, text in enumerate(bullets):
        y = 390 + index * 80
        draw.ellipse((1090, y + 7, 1110, y + 27), fill=(24, 137, 166))
        label(draw, (1132, y), text, 23, color=(55, 79, 91))
    rounded(draw, (1078, 710, 1535, 770), 24, (224, 246, 246), (133, 205, 209), 2)
    label(draw, (1307, 740), "小尺度 · 高感知 · 可持续", 22, color=(17, 111, 123), bold=True, anchor="mm")
    image.save(path, format="PNG", compress_level=9)
    return [("title", "城市微更新观察"), ("subtitle", "在有限空间里创造更友好的公共体验"),
            ("section", "观察结论"), *[(f"bullet-{i + 1}", text) for i, text in enumerate(bullets)],
            ("footer", "小尺度 · 高感知 · 可持续")]


def draw_b04(path: Path) -> list[tuple[str, str]]:
    image, draw = canvas((73, 99, 210))
    label(draw, (82, 62), "需求到交付的闭环流程", 56, bold=True)
    label(draw, (84, 137), "分支评审、结果汇合与反馈回路必须保持连通", 25, color=(76, 91, 140))
    nodes = {
        "需求输入": (90, 360, 335, 500),
        "方案设计": (440, 235, 700, 375),
        "风险评审": (440, 555, 700, 695),
        "统一执行": (820, 360, 1080, 500),
        "结果验收": (1245, 360, 1515, 500),
    }
    fills = [(235, 243, 255), (236, 248, 244), (255, 242, 224), (239, 239, 255), (229, 248, 244)]
    for index, (name, box) in enumerate(nodes.items()):
        rounded(draw, box, 28, fills[index], (143, 179, 231), 4)
        label(draw, ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2), name, 28, bold=True, anchor="mm")
    arrow(draw, [(335, 430), (390, 430), (390, 305), (440, 305)])
    arrow(draw, [(335, 430), (390, 430), (390, 625), (440, 625)])
    arrow(draw, [(700, 305), (760, 305), (760, 430), (820, 430)])
    arrow(draw, [(700, 625), (760, 625), (760, 430), (820, 430)])
    arrow(draw, [(1080, 430), (1245, 430)])
    arrow(draw, [(1380, 500), (1380, 785), (210, 785), (210, 500)], (232, 118, 63), 7)
    label(draw, (800, 835), "验收反馈回到需求输入", 24, color=(184, 78, 31), bold=True, anchor="mm")
    label(draw, (562, 405), "并行", 20, color=(86, 104, 144), anchor="mm")
    label(draw, (758, 462), "汇合", 20, color=(86, 104, 144), anchor="mm")
    image.save(path, format="PNG", compress_level=9)
    return [("title", "需求到交付的闭环流程"), ("subtitle", "分支评审、结果汇合与反馈回路必须保持连通"),
            *[(f"node-{i + 1}", name) for i, name in enumerate(nodes)],
            ("parallel", "并行"), ("merge", "汇合"), ("feedback", "验收反馈回到需求输入")]


def draw_b06(path: Path) -> list[tuple[str, str]]:
    image, draw = canvas((45, 123, 198))
    label(draw, (836, 190), "保持简单，才能持续复用", 60, bold=True, anchor="mm")
    label(draw, (836, 283), "Zero-Asset Baseline", 28, color=(76, 109, 143), anchor="mm")
    rounded(draw, (266, 410, 740, 610), 38, (236, 246, 255), (149, 196, 237), 3)
    rounded(draw, (932, 410, 1406, 610), 38, (236, 250, 243), (150, 213, 181), 3)
    label(draw, (503, 482), "结构清晰", 35, bold=True, anchor="mm")
    label(draw, (503, 548), "只使用原生文字与形状", 22, color=(70, 91, 116), anchor="mm")
    label(draw, (1169, 482), "路径最短", 35, bold=True, anchor="mm")
    label(draw, (1169, 548), "不产生裁切或图片资产", 22, color=(70, 91, 116), anchor="mm")
    draw.line((740, 510, 932, 510), fill=(91, 139, 199), width=7)
    arrow(draw, [(820, 510), (932, 510)], (91, 139, 199), 7)
    label(draw, (836, 745), "输入明确 → 构建直接 → 证据完整", 28, color=(29, 92, 164), bold=True, anchor="mm")
    image.save(path, format="PNG", compress_level=9)
    return [("title", "保持简单，才能持续复用"), ("subtitle", "Zero-Asset Baseline"),
            ("left-title", "结构清晰"), ("left-body", "只使用原生文字与形状"),
            ("right-title", "路径最短"), ("right-body", "不产生裁切或图片资产"),
            ("footer", "输入明确 → 构建直接 → 证据完整")]


def request(case_id: str, topic: str, requirements: list[str]) -> dict:
    return {
        "schema_version": "1.3",
        "task_id": f"p0-{case_id.lower()}",
        "topic": topic,
        "source_image": "source.png",
        "output_ratio": RATIO,
        "typography_interaction": "match-source",
        "typography": {
            "title_font": "Microsoft YaHei",
            "title_size_pt": 34,
            "body_font": "Microsoft YaHei",
            "body_size_pt": 18,
        },
        "editability_policy": "text-and-structure",
        "user_requirements": requirements,
        "review_policy": {
            "max_iterations": 3,
            "pass_score": 90,
            "warning_floor_score": 85,
            "min_content_accuracy": 98,
            "required_editability_score": 100,
            "critical_policy": "by_recoverability",
        },
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_case(output_root: Path, case_id: str, b05_source: Path | None) -> None:
    case_root = output_root / case_id
    input_root = case_root / "input"
    evidence_root = case_root / "evidence"
    input_root.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)
    source = input_root / "source.png"
    if case_id == "B01":
        topic, items = "项目启动简报", draw_b01(source)
        requirements = ["Keep all readable text editable.", "Rebuild all cards and basic geometry as native PowerPoint shapes."]
    elif case_id == "B02":
        topic, items = "团队能力地图", draw_b02(source)
        requirements = ["Keep all readable text and cards editable.", "Preserve the six polished icons as cropped runtime assets; do not replace them with Unicode glyphs."]
    elif case_id == "B03":
        topic, items = "城市微更新观察", draw_b03(source)
        requirements = ["Keep all readable text editable.", "Crop the original landscape panel as a runtime image asset and preserve its focal subject and alignment."]
    elif case_id == "B04":
        topic, items = "需求到交付的闭环流程", draw_b04(source)
        requirements = ["Keep all labels and nodes editable.", "Rebuild branch, merge, arrow direction, endpoints, and feedback loop with native connectors."]
    elif case_id == "B05":
        if b05_source is None or not b05_source.is_file():
            raise FileNotFoundError("B05 requires --b05-source pointing to the tracked public AI learning loop image")
        shutil.copyfile(b05_source, source)
        topic = "AI 驱动的学习闭环"
        items = [
            ("title", "AI 驱动的学习闭环"), ("subtitle", "让目标、行动与反馈持续连接"),
            ("input", "学习输入"), ("input-1", "课程资料"), ("input-2", "学习行为"), ("input-3", "评价标准"),
            ("output", "智能输出"), ("output-1", "知识地图"), ("output-2", "能力画像"), ("output-3", "行动建议"),
            ("step-1", "明确目标"), ("step-1-body", "定义成果"),
            ("step-2", "连接资源"), ("step-2-body", "获取知识"),
            ("step-3", "智能练习"), ("step-3-body", "即时支持"),
            ("step-4", "同伴协作"), ("step-4-body", "共同建构"),
            ("step-5", "多元评估"), ("step-5-body", "发现差距"),
            ("step-6", "迭代提升"), ("step-6-body", "持续成长"),
            ("center", "学习者"), ("footer", "每一次反馈，都让下一轮学习更精准"),
        ]
        requirements = ["Keep every readable label editable.", "Crop polished source icons as independent runtime assets.", "Preserve the closed directional learning loop and visual hierarchy."]
    else:
        topic, items = "Zero-Asset Baseline", draw_b06(source)
        requirements = ["Use native editable text, shapes, and connectors only.", "Produce zero crop entries and zero runtime image or SVG assets."]

    write_json(input_root / "request.json", request(case_id, topic, requirements))
    write_json(
        evidence_root / "baseline-source-content.json",
        {
            "artifact_role": "baseline_evidence",
            "runtime_contract": False,
            "case_id": case_id,
            "revision": 1,
            "status": "frozen",
            "source_sha256": sha256(source),
            "text_items": [{"id": item_id, "text": text} for item_id, text in items],
        },
    )
    write_json(
        case_root / "case-definition.json",
        {
            "case_id": case_id,
            "category": {
                "B01": "text_and_basic_shapes", "B02": "cards_and_icons", "B03": "image_and_text",
                "B04": "flow_and_connectors", "B05": "complex_infographic", "B06": "zero_asset",
            }[case_id],
            "source_policy": "tracked_public_reuse" if case_id == "B05" else "original_deterministic_fixture",
            "width_px": WIDTH,
            "height_px": HEIGHT,
            "max_visual_revisions": 2,
            "max_total_iterations": 3,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic P0 Baseline source fixtures.")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--b05-source", type=Path, required=True)
    args = parser.parse_args()
    for case_id in CASES:
        build_case(args.output_root.resolve(), case_id, args.b05_source.resolve())
    result = {case_id: sha256(args.output_root.resolve() / case_id / "input" / "source.png") for case_id in CASES}
    print(json.dumps({"status": "ok", "source_sha256": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
