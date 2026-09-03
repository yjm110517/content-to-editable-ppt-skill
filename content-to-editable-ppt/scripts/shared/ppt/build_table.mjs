import { basePosition, marginOptions } from "./apply_text_layout.mjs";

function cellOptions(element, rowIndex, merge) {
  const header = rowIndex < element.header_row_count;
  return {
    fontFace: element.font_face,
    fontSize: element.font_size_pt,
    color: element.color.replace(/^#/, "").toUpperCase(),
    bold: header && element.header_bold,
    align: element.align,
    valign: element.valign,
    margin: marginOptions(element.margin_in),
    fill: { color: (header ? element.header_fill : element.body_fill).replace(/^#/, "").toUpperCase() },
    border: { type: "solid", color: element.border_color.replace(/^#/, "").toUpperCase(), pt: element.border_width_pt },
    ...(merge ? { rowspan: merge.row_span, colspan: merge.column_span } : {}),
  };
}

function mergeMaps(merges) {
  const anchors = new Map();
  const covered = new Set();
  for (const merge of merges) {
    anchors.set(`${merge.row}:${merge.column}`, merge);
    for (let row = merge.row; row < merge.row + merge.row_span; row += 1) {
      for (let column = merge.column; column < merge.column + merge.column_span; column += 1) {
        if (row !== merge.row || column !== merge.column) covered.add(`${row}:${column}`);
      }
    }
  }
  return { anchors, covered };
}

export function buildTable(slide, element) {
  const { anchors, covered } = mergeMaps(element.merges);
  const rows = element.grid.map((row, rowIndex) => row.flatMap((value, columnIndex) => {
    const key = `${rowIndex}:${columnIndex}`;
    if (covered.has(key)) return [];
    const merge = anchors.get(key);
    return [{ text: value, options: cellOptions(element, rowIndex, merge) }];
  }));
  slide.addTable(rows, {
    ...basePosition(element, `ivt:${element.id}`),
    colW: element.column_widths,
    rowH: element.row_heights,
    autoPage: false,
    border: { type: "solid", color: element.border_color.replace(/^#/, "").toUpperCase(), pt: element.border_width_pt },
  });
}
