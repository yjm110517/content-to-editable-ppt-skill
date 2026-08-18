import { mkdir, mkdtemp, rename, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import PptxGenJS from "pptxgenjs";

import { BuildError, failure, readJson, sha256Bytes, sha256File, success } from "./build_common.mjs";
import { buildSlideIntoPresentation } from "./shared/ppt/build_slide_into_presentation.mjs";
import { normalizePptx } from "./shared/ppt/normalize_pptx.mjs";
import { DIMENSIONS, resolveReconstructionAssets, specToLayout } from "./shared/ppt/reconstruction_layout.mjs";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT = "build_reconstruction_page";

function parse(argv) {
  const allowed = new Set(["spec", "asset-manifest", "evidence-root", "output", "report", "python", "schema-dir"]); const values = {};
  for (let index = 0; index < argv.length; index += 2) { const option = argv[index]; const value = argv[index + 1]; if (!option?.startsWith("--") || value === undefined || value.startsWith("--")) throw new BuildError(`invalid CLI argument near ${option ?? "<end>"}`, { exitCode: 2, category: "cli_error" }); const name = option.slice(2); if (!allowed.has(name) || Object.hasOwn(values, name)) throw new BuildError(`unknown or duplicate option: ${option}`, { exitCode: 2, category: "cli_error" }); values[name] = value; }
  for (const name of ["spec", "asset-manifest", "evidence-root", "output", "report"]) if (!values[name]) throw new BuildError(`missing --${name}`, { exitCode: 2, category: "cli_error" });
  return values;
}

function validate(kind, input, python, schemaDir) {
  const args = [path.join(SCRIPT_DIR, "validate_spec.py"), `--${kind.replaceAll("_", "-")}`, input]; if (schemaDir) args.push("--schema-dir", schemaDir);
  const run = spawnSync(python, args, { windowsHide: true, encoding: "utf8" }); if (run.status !== 0) throw new BuildError(`contract validation failed: ${run.stdout || run.stderr}`, { category: "contract_error", target: input });
}

async function assertOutput(pathValue) { try { await stat(pathValue); throw new BuildError("output already exists", { category: "output_collision", target: pathValue }); } catch (error) { if (error instanceof BuildError) throw error; if (error.code !== "ENOENT") throw error; } }

export async function buildPage(args) {
  const python = args.python ?? process.env.IVT_PYTHON ?? "python"; validate("visual_reconstruction_spec", args.spec, python, args["schema-dir"]); validate("reconstruction_asset_manifest", args["asset-manifest"], python, args["schema-dir"]);
  await assertOutput(args.output); await assertOutput(args.report);
  const spec = await readJson(args.spec); const assetManifest = await readJson(args["asset-manifest"]); if (spec.deck_id !== assetManifest.deck_id) throw new BuildError("asset manifest deck mismatch", { category: "authority_mismatch", target: args["asset-manifest"] });
  const layout = specToLayout(spec); const assets = await resolveReconstructionAssets(assetManifest, args["evidence-root"]); const dimensions = DIMENSIONS[spec.output_ratio];
  const pptx = new PptxGenJS(); pptx.defineLayout({ name: "P4_CUSTOM", width: dimensions.width_in, height: dimensions.height_in }); pptx.layout = "P4_CUSTOM"; pptx.author = "Content to Editable PPT Skill"; pptx.title = `${spec.deck_id} ${spec.slide_id} reconstruction candidate`; pptx.subject = "P4 constrained reconstruction"; pptx.company = ""; pptx.revision = "1";
  const slide = pptx.addSlide(); const built = await buildSlideIntoPresentation({ pptx, slide, layout, assets });
  const raw = await pptx.write({ outputType: "nodebuffer", compression: true }); const bytes = await normalizePptx(Buffer.from(raw), 1); const outputHash = sha256Bytes(bytes);
  const counts = Object.fromEntries(["native_text", "native_shape", "native_chart", "sanitized_svg", "reusable_raster", "generated_foreground"].map((kind) => [kind, spec.elements.filter((item) => item.reconstruction_class === kind).length]));
  const report = { schema_version: "1.0", artifact_type: "reconstruction_build_report", deck_id: spec.deck_id, slide_id: spec.slide_id, spec_sha256: await sha256File(args.spec), output_pptx_sha256: outputHash, expected_element_count: spec.elements.length, built_element_count: built.builtIds.size, native_text_count: counts.native_text, native_shape_count: counts.native_shape, native_chart_count: counts.native_chart, sanitized_svg_count: counts.sanitized_svg, raster_count: counts.reusable_raster + counts.generated_foreground, full_slide_raster_substitution: false, status: "built" };
  await mkdir(path.dirname(path.resolve(args.output)), { recursive: true });
  const stage = await mkdtemp(path.join(path.dirname(path.resolve(args.output)), ".p4-page-")); try { const stagedPptx = path.join(stage, path.basename(args.output)); const stagedReport = path.join(stage, path.basename(args.report)); await writeFile(stagedPptx, bytes); await writeFile(stagedReport, `${JSON.stringify(report, null, 2)}\n`, "utf8"); validate("reconstruction_build_report", stagedReport, python, args["schema-dir"]); await rename(stagedPptx, args.output); await rename(stagedReport, args.report); } finally { await rm(stage, { recursive: true, force: true }); }
  return report;
}

async function main() { let args; try { args = parse(process.argv.slice(2)); const report = await buildPage(args); console.log(JSON.stringify(success(COMPONENT, { output: path.resolve(args.output), report: path.resolve(args.report), pptx_sha256: report.output_pptx_sha256 }, specRun(args), 1))); return 0; } catch (error) { console.log(JSON.stringify(failure(COMPONENT, error, "p4", 1))); return error instanceof BuildError ? error.exitCode : 70; } }
function specRun(args) { return path.basename(args.spec ?? "p4"); }
if (path.resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url)) process.exitCode = await main();
