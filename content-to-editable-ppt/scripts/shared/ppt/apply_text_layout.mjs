export function normalizeColor(value, explicitTransparency) {
  const raw = value ?? "#000000";
  const cleaned = raw.startsWith("#") ? raw.slice(1).toUpperCase() : raw.toUpperCase();
  if (cleaned.length === 8) {
    const alpha = Number.parseInt(cleaned.slice(6), 16);
    return { color: cleaned.slice(0, 6), transparency: Math.round((1 - alpha / 255) * 100) };
  }
  return explicitTransparency === undefined ? { color: cleaned } : { color: cleaned, transparency: explicitTransparency };
}

export function marginOptions(margin) {
  if (margin === undefined) return undefined;
  if (Array.isArray(margin)) return margin.map((value) => value * 72);
  return margin * 72;
}

export function pick(value, fallback) { return value === undefined ? fallback : value; }

export function styleFor(layout, element) { return element.style_ref ? layout.styles[element.style_ref] : {}; }

function bulletOptions(bullet) {
  if (bullet === undefined) return undefined;
  if (bullet === true) return true;
  return { type: bullet.type, characterCode: bullet.character_code, numberType: bullet.style, numberStartAt: bullet.start_at, indent: bullet.indent_pt };
}

function textRunOptions(run, element, style) {
  const fontFace = pick(run.font_face, pick(element.font_face, style.font_face));
  const fontSize = pick(run.font_size_pt, pick(element.font_size_pt, style.font_size_pt));
  const colorValue = pick(run.color, pick(element.color, style.color));
  const transparency = pick(run.transparency, pick(element.transparency, style.transparency));
  return { fontFace, fontSize, ...normalizeColor(colorValue, transparency), bold: pick(run.bold, pick(element.bold, style.bold)), italic: pick(run.italic, pick(element.italic, style.italic)), underline: pick(run.underline, pick(element.underline, style.underline)), lang: pick(run.language, pick(element.language, style.language)), breakLine: run.break_line, bullet: bulletOptions(pick(run.bullet, pick(element.bullet, style.bullet))) };
}

export function basePosition(element, objectName) { return { x: element.x, y: element.y, w: element.w, h: element.h, rotate: element.rotation ?? 0, objectName }; }

export function applyTextLayout(slide, layout, element, typography) {
  const style = styleFor(layout, element);
  const rawRuns = element.runs ?? [{ text: element.text }];
  const runs = rawRuns.map((run, index) => {
    const options = textRunOptions(run, element, style);
    const source = run.font_face ? "run" : element.font_face ? "element" : "style";
    typography.font_resolutions.push({ element_id: element.id, run_index: index, font_face: options.fontFace, font_size_pt: options.fontSize, source });
    if (source === "run") typography.explicit_run_font_count += 1; else typography.inherited_run_font_count += 1;
    typography.run_count += 1;
    return { text: run.text, options };
  });
  const fit = pick(element.fit, style.fit) ?? "none";
  if (fit !== "none") typography.non_default_fit_elements.push(element.id);
  slide.addText(runs, { ...basePosition(element, `ivt:${element.id}`), align: pick(element.align, style.align) ?? "left", valign: pick(element.valign, style.valign) ?? "top", margin: marginOptions(pick(element.margin_in, style.margin_in) ?? 0), lineSpacing: pick(element.line_spacing_pt, style.line_spacing_pt), lineSpacingMultiple: pick(element.line_spacing_multiple, style.line_spacing_multiple), paraSpaceBeforePt: pick(element.para_space_before_pt, style.para_space_before_pt), paraSpaceAfterPt: pick(element.para_space_after_pt, style.para_space_after_pt), fit: fit === "resize-shape" ? "resize" : fit, breakLine: false, fill: { color: "FFFFFF", transparency: 100 }, line: { color: "FFFFFF", transparency: 100, width: 0 } });
  typography.text_element_count += 1;
}
