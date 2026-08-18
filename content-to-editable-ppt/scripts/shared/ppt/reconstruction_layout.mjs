import { realpath, stat } from "node:fs/promises";
import path from "node:path";
import { BuildError, sha256File } from "../../build_common.mjs";

export const DIMENSIONS = { "16:9": { width_in: 13.333, height_in: 7.5, width_px: 1600, height_px: 900 }, "4:3": { width_in: 10, height_in: 7.5, width_px: 1200, height_px: 900 } };

function position(element, dimensions) {
  const box = element.normalized_bbox;
  return { x: box.x * dimensions.width_in / 10000, y: box.y * dimensions.height_in / 10000, w: box.w * dimensions.width_in / 10000, h: box.h * dimensions.height_in / 10000, z_index: element.z_index };
}

function freshShadow(token) {
  if (!token || token === "none") return undefined;
  return token === "medium" ? { color: "#000000", opacity: 0.18, blur_pt: 10, angle: 45, offset_pt: 3 } : { color: "#000000", opacity: 0.14, blur_pt: 6, angle: 45, offset_pt: 2 };
}

function shapeElement(item, dimensions) {
  const impl = item.implementation; const style = impl.style_seed ?? {};
  const shapeMap = { rect: "rect", rounded_rect: "roundRect", ellipse: "ellipse", chevron: "chevron", triangle: "triangle", simple_polygon: "hexagon" };
  if (["line", "arrow"].includes(impl.shape_kind)) return { id: item.element_id, type: "line", ...position(item, dimensions), editable: true, geometry: "straight", line: { color: style.border_color ?? "#2457C5", width_pt: 1.5, end_arrow: impl.shape_kind === "arrow" ? "triangle" : "none" } };
  return { id: item.element_id, type: "shape", ...position(item, dimensions), editable: true, shape: shapeMap[impl.shape_kind] ?? "rect", fill: { color: style.fill_color ?? "#F2F5FA", transparency: Math.max(0, Math.min(100, Math.round(100 - (style.opacity_milli ?? 1000) / 10))) }, line: { color: style.border_color ?? "#2457C5", width_pt: style.border_token === "none" ? 0 : 1 }, shadow: freshShadow(style.shadow_token) };
}

function textElement(item, dimensions) {
  const impl = item.implementation; const weight = impl.weight;
  return { id: item.element_id, type: "text", ...position(item, dimensions), editable: true, text: impl.text, content_ref: impl.content_ref, font_face: impl.font_family, font_size_pt: impl.font_size_pt, color: impl.color, bold: weight === "bold" || weight === "semibold", align: impl.alignment, valign: impl.vertical_alignment === "middle" ? "mid" : impl.vertical_alignment, margin_in: (impl.margin_milli ?? 0) / 1000, line_spacing_pt: impl.font_size_pt * (impl.line_spacing_milli ?? 1200) / 1000, fit: "shrink" };
}

function chartElement(item, dimensions) {
  const chart = item.implementation.chart_spec;
  return { id: item.element_id, type: "chart", ...position(item, dimensions), editable: true, chart_type: chart.chart_type, categories: chart.categories, series: chart.series.map((series) => ({ name: series.name, values: series.scaled_integer_values })), value_scale: chart.value_scale, show_legend: chart.show_legend, show_value: chart.show_value, number_format: chart.number_format, color_tokens: chart.color_tokens };
}

function imageElement(item, dimensions) { return { id: item.element_id, type: "image", ...position(item, dimensions), editable: false, asset_id: item.implementation.asset_ref, fit: item.implementation.fit ?? "contain", preserve_aspect_ratio: true, contains_text: false, alt_text: item.implementation.asset_ref }; }

export function specToLayout(spec) {
  const dimensions = DIMENSIONS[spec.output_ratio];
  if (!dimensions) throw new BuildError("unsupported output ratio", { category: "unsupported_ratio", target: spec.output_ratio });
  const elements = [];
  for (const item of spec.elements) {
    const kind = item.reconstruction_class;
    if (kind === "native_text") elements.push(textElement(item, dimensions));
    else if (kind === "native_shape") elements.push(shapeElement(item, dimensions));
    else if (kind === "native_chart") elements.push(chartElement(item, dimensions));
    else if (["sanitized_svg", "reusable_raster", "generated_foreground"].includes(kind)) elements.push(imageElement(item, dimensions));
    else if (kind === "generated_background") {
      if (item.implementation.background_strategy === "approved_background_raster") elements.push(imageElement(item, dimensions));
      else elements.push({ id: item.element_id, type: "shape", ...position(item, dimensions), editable: true, shape: "rect", fill: { color: item.implementation.fill_color }, line: { color: item.implementation.fill_color, width_pt: 0 } });
    } else if (kind === "decorative_approximation") {
      if (item.implementation.approximation_kind === "corner_arc") elements.push({ id: item.element_id, type: "line", ...position(item, dimensions), editable: true, geometry: "arc", line: { color: item.implementation.fill_color, transparency: Math.max(0, 100 - Math.round((item.implementation.opacity_milli ?? 850) / 10)), width_pt: 12 } });
      else elements.push({ id: item.element_id, type: "shape", ...position(item, dimensions), editable: true, shape: "ellipse", fill: { color: item.implementation.fill_color, transparency: Math.max(0, 100 - Math.round((item.implementation.opacity_milli ?? 180) / 10)) }, line: { color: item.implementation.fill_color, transparency: 100, width_pt: 0 } });
    } else throw new BuildError("unsupported reconstruction class", { category: "unsupported_element", target: kind });
  }
  return { schema_version: "p4-internal-1", slide: { width_in: dimensions.width_in, height_in: dimensions.height_in, background: "#FFFFFF" }, styles: {}, elements, metadata: { topic: spec.deck_id, iteration: 1 }, source: { width_px: dimensions.width_px, height_px: dimensions.height_px } };
}

export async function resolveReconstructionAssets(assetManifest, evidenceRoot) {
  const canonicalRoot = await realpath(evidenceRoot);
  const assets = [];
  for (const item of assetManifest.assets) {
    const resolved = path.resolve(canonicalRoot, ...item.path.split("/"));
    const relative = path.relative(canonicalRoot, resolved);
    if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) throw new BuildError("asset path escapes evidence root", { category: "path_escape", target: item.path });
    const fileStat = await stat(resolved);
    if (await sha256File(resolved) !== item.sha256) throw new BuildError("reconstruction asset hash mismatch", { category: "hash_conflict", target: item.asset_ref });
    assets.push({ id: item.asset_ref, type: item.media_type === "image/svg+xml" ? "svg" : item.media_type === "image/jpeg" ? "jpeg" : "png", path: resolved, sha256: item.sha256, size_bytes: fileStat.size });
  }
  return new Map(assets.map((item) => [item.id, item]));
}
