import { basePosition, normalizeColor, styleFor } from "./apply_text_layout.mjs";

export function fillOptions(fill) { return fill ? normalizeColor(fill.color, fill.transparency) : { color: "FFFFFF", transparency: 100 }; }
export function lineOptions(line) { return line ? { ...normalizeColor(line.color, line.transparency), width: line.width_pt, dashType: line.dash ?? "solid", beginArrowType: line.begin_arrow ?? "none", endArrowType: line.end_arrow ?? "none" } : { color: "FFFFFF", transparency: 100, width: 0 }; }
export function shadowOptions(shadow) { return shadow ? { type: "outer", color: shadow.color.replace(/^#/, ""), opacity: shadow.opacity, blur: shadow.blur_pt, angle: shadow.angle, offset: shadow.offset_pt, rotateWithShape: false } : undefined; }
export function buildShape(pptx, slide, layout, element) {
  const style = styleFor(layout, element);
  slide.addShape(pptx.ShapeType[element.shape], { ...basePosition(element, `ivt:${element.id}`), fill: fillOptions(element.fill ?? style.fill), line: lineOptions(element.line ?? style.line), shadow: shadowOptions(element.shadow ?? style.shadow) });
}
