import { basePosition } from "./apply_text_layout.mjs";

export function buildChart(pptx, slide, element) {
  const chartType = element.chart_type === "donut" ? pptx.ChartType.doughnut : element.chart_type === "line" ? pptx.ChartType.line : pptx.ChartType.bar;
  const scale = element.value_scale;
  const data = element.series.map((series) => ({ name: series.name, labels: element.categories, values: series.values.map((value) => value / scale) }));
  slide.addChart(chartType, data, { ...basePosition(element, `ivt:${element.id}`), catAxisLabelFontFace: element.font_face ?? "Microsoft YaHei", valAxisLabelFontFace: element.font_face ?? "Microsoft YaHei", showLegend: element.show_legend ?? true, showValue: element.show_value ?? false, showTitle: false, showCatName: false, showSerName: false, showPercent: false, showCategoryName: false, showBorder: false, chartColors: element.color_tokens?.map((value) => value.replace(/^#/, "").toUpperCase()), valGridLine: { color: "D9D9D9", width: 1 }, valAxisLabelFormatCode: element.number_format ?? "General", ...(element.category_axis_label ? { catAxisTitle: element.category_axis_label, showCatAxisTitle: true } : {}), ...(element.value_axis_label ? { valAxisTitle: element.value_axis_label, showValAxisTitle: true } : {}), ...(element.chart_type === "vertical_bar" ? { barDir: "col" } : element.chart_type === "horizontal_bar" ? { barDir: "bar" } : {}) });
}
