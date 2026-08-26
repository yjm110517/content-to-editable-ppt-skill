import { mkdir, mkdtemp, rename, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import PptxGenJS from "pptxgenjs";

import { BuildError, failure, readJson, sha256Bytes, sha256File, success } from "./build_common.mjs";
import { buildSlideIntoPresentation } from "./shared/ppt/build_slide_into_presentation.mjs";
import { normalizePptx } from "./shared/ppt/normalize_pptx.mjs";


const COMPONENT = "build_deck";
const DIMENSIONS = { "16:9": { width: 13.333, height: 7.5 }, "4:3": { width: 10, height: 7.5 } };


function parse(argv) {
  const allowed = new Set(["request", "staged-assets", "output", "report"]);
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const option = argv[index], value = argv[index + 1];
    if (!option?.startsWith("--") || value === undefined || value.startsWith("--")) throw new BuildError(`invalid CLI argument near ${option ?? "<end>"}`, { exitCode: 2, category: "cli_error" });
    const name = option.slice(2);
    if (!allowed.has(name) || Object.hasOwn(values, name)) throw new BuildError(`unknown or duplicate option: ${option}`, { exitCode: 2, category: "cli_error" });
    values[name] = value;
  }
  for (const name of allowed) if (!values[name]) throw new BuildError(`missing --${name}`, { exitCode: 2, category: "cli_error" });
  return values;
}


async function assertMissing(value) {
  try { await stat(value); throw new BuildError("output already exists", { exitCode: 9, category: "output_collision", target: value }); }
  catch (error) { if (error instanceof BuildError) throw error; if (error.code !== "ENOENT") throw error; }
}


export async function buildDeck(args) {
  await assertMissing(args.output); await assertMissing(args.report);
  const request = await readJson(args.request), staged = await readJson(args["staged-assets"]);
  if (!Array.isArray(staged) || !DIMENSIONS[request.output_ratio]) throw new BuildError("invalid direct deck build inputs", { category: "contract_error" });
  const assets = new Map(staged.map((item) => [item.id, item]));
  if (assets.size !== staged.length) throw new BuildError("duplicate staged asset id", { category: "contract_error" });
  const dimensions = DIMENSIONS[request.output_ratio];
  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: "DIRECT_DECK", width: dimensions.width, height: dimensions.height });
  pptx.layout = "DIRECT_DECK";
  pptx.author = "Content to Editable PPT Skill";
  pptx.title = request.topic;
  pptx.subject = request.objective;
  pptx.company = "";
  pptx.revision = "1";
  const pages = [];
  for (const page of [...request.slides].sort((left, right) => left.order - right.order)) {
    const slide = pptx.addSlide();
    const layout = { slide: { width_in: dimensions.width, height_in: dimensions.height, background: page.background }, styles: request.styles, elements: page.elements };
    const built = await buildSlideIntoPresentation({ pptx, slide, layout, assets });
    pages.push({
      slide_id: page.slide_id,
      order: page.order,
      expected_element_ids: built.expectedIds,
      element_map: built.elementMap,
      used_asset_ids: [...built.usedAssets.keys()].sort(),
      text_element_count: built.typography.text_element_count,
    });
  }
  const raw = await pptx.write({ outputType: "nodebuffer", compression: true });
  const bytes = await normalizePptx(Buffer.from(raw), pages.length);
  const report = {
    schema_version: "1.0",
    artifact_type: "direct_deck_build_report",
    deck_id: request.deck_id,
    request_sha256: await sha256File(args.request),
    output_name: request.output_name,
    pptx_sha256: sha256Bytes(bytes),
    slide_count: pages.length,
    slide_order: pages.map((page) => page.slide_id),
    pages,
    staged_assets: staged.map((item) => ({ asset_id: item.id, source_sha256: item.source_sha256, staged_sha256: item.sha256, media_type: item.media_type })),
    status: "built",
  };
  const parent = path.dirname(path.resolve(args.output));
  await mkdir(parent, { recursive: true });
  const temporary = await mkdtemp(path.join(parent, ".direct-deck-"));
  try {
    const stagedPptx = path.join(temporary, path.basename(args.output));
    const stagedReport = path.join(temporary, path.basename(args.report));
    await writeFile(stagedPptx, bytes);
    await writeFile(stagedReport, `${JSON.stringify(report, null, 2)}\n`, "utf8");
    await rename(stagedPptx, args.output);
    await rename(stagedReport, args.report);
  } finally { await rm(temporary, { recursive: true, force: true }); }
  return report;
}


async function main() {
  let args;
  try {
    args = parse(process.argv.slice(2));
    const report = await buildDeck(args);
    console.log(JSON.stringify(success(COMPONENT, { output: path.resolve(args.output), report: path.resolve(args.report), pptx_sha256: report.pptx_sha256 }, requestRunId(args), 1)));
    return 0;
  } catch (error) {
    console.log(JSON.stringify(failure(COMPONENT, error, args?.request ?? "direct-deck", 1)));
    return error instanceof BuildError ? error.exitCode : 70;
  }
}


function requestRunId(args) { return path.basename(args.request, path.extname(args.request)); }


if (path.resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url)) process.exitCode = await main();
