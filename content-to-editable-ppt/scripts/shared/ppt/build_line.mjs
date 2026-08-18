import { BuildError } from "../../build_common.mjs";
import { basePosition } from "./apply_text_layout.mjs";
import { lineOptions } from "./build_shape.mjs";

export function buildLine(pptx, slide, element) {
  const geometry = element.geometry ?? "straight";
  if (geometry === "curve") {
    const { start, control1, control2, end } = element.curve;
    if ([start, control1, control2, end].some((point) => point.x > element.w || point.y > element.h)) throw new BuildError("curve point exceeds the element bounding box", { category: "invalid_curve", target: element.id });
    slide.addShape(pptx.ShapeType.custGeom, { ...basePosition(element, `ivt:${element.id}`), fill: { color: "FFFFFF", transparency: 100 }, line: lineOptions(element.line), points: [{ x: start.x, y: start.y, moveTo: true }, { x: end.x, y: end.y, curve: { type: "cubic", x1: control1.x, y1: control1.y, x2: control2.x, y2: control2.y } }] });
    return;
  }
  const shapeType = geometry === "arc" ? pptx.ShapeType.arc : pptx.ShapeType.line;
  slide.addShape(shapeType, { ...basePosition(element, `ivt:${element.id}`), fill: { color: "FFFFFF", transparency: 100 }, line: lineOptions(element.line) });
}
