import { BuildError } from "../../build_common.mjs";
import { buildChart } from "./build_chart.mjs";
import { buildImage } from "./build_image.mjs";
import { buildLine } from "./build_line.mjs";
import { buildShape } from "./build_shape.mjs";
import { buildText } from "./build_text.mjs";

export function stableBuildOrder(elements) { return elements.map((element, index) => ({ element, index })).sort((left, right) => left.element.z_index - right.element.z_index || left.index - right.index); }
export function createTypographyReport() { return { text_element_count: 0, run_count: 0, explicit_run_font_count: 0, inherited_run_font_count: 0, unresolved_font_count: 0, non_default_fit_elements: [], font_resolutions: [] }; }

export async function buildSlideIntoPresentation({ pptx, slide, layout, assets }) {
  slide.background = { color: layout.slide.background.replace(/^#/, "").toUpperCase() };
  const usedAssets = new Map();
  const typography = createTypographyReport();
  const ordered = stableBuildOrder(layout.elements);
  const elementMap = [];
  const connections = [];
  for (const { element } of ordered) {
    if (element.type === "text") buildText(slide, layout, element, typography);
    else if (element.type === "shape") buildShape(pptx, slide, layout, element);
    else if (element.type === "line") { buildLine(pptx, slide, element); connections.push({ element_id: element.id, from_id: element.from_id ?? null, to_id: element.to_id ?? null }); }
    else if (element.type === "image") await buildImage(slide, element, assets, usedAssets);
    else if (element.type === "chart") buildChart(pptx, slide, element);
    else throw new BuildError("unsupported element type", { category: "unsupported_element", target: element.type });
    elementMap.push({ element_id: element.id, type: element.type, object_names: [`ivt:${element.id}`], object_count: 1 });
  }
  const builtIds = new Set(elementMap.map((item) => item.element_id));
  const expectedIds = layout.elements.map((item) => item.id);
  const missing = expectedIds.filter((id) => !builtIds.has(id));
  const unexpected = [...builtIds].filter((id) => !expectedIds.includes(id));
  if (missing.length || unexpected.length || builtIds.size !== expectedIds.length) throw new BuildError("element reconciliation failed", { exitCode: 6, category: "element_reconciliation" });
  return { ordered, elementMap: elementMap.sort((left, right) => expectedIds.indexOf(left.element_id) - expectedIds.indexOf(right.element_id)), usedAssets, typography, connections, expectedIds, builtIds, missing, unexpected };
}
