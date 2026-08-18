import { spawn } from "node:child_process";
import { mkdir, mkdtemp, rename, rm, unlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import PptxGenJS from "pptxgenjs";

import { BuildError, enforceIterationBoundary, failure, logEvent, parseArgs, readJson, sha256Bytes, sha256File, success } from "./build_common.mjs";
import { normalizeColor } from "./shared/ppt/apply_text_layout.mjs";
import { buildSlideIntoPresentation, stableBuildOrder } from "./shared/ppt/build_slide_into_presentation.mjs";
import { verifyAsset as verifyResolvedAsset } from "./shared/ppt/verify_asset.mjs";
import { normalizePptx } from "./shared/ppt/normalize_pptx.mjs";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const COMPONENT = "build_slide";

export { normalizeColor, stableBuildOrder, verifyResolvedAsset };

function runProcess(executable, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, { windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (value) => { stdout += value; });
    child.stderr.on("data", (value) => { stderr += value; });
    child.on("error", (error) => reject(new BuildError(`Python runtime is unavailable: ${error.message}`, { exitCode: 5, category: "environment_error", target: executable })));
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

async function validateAndResolveAssets(args, python) {
  const command = [path.join(SCRIPT_DIR, "validate_assets.py"), "--asset-dir", args["asset-dir"], "--asset-manifest", args["asset-manifest"], "--layout", args.layout, "--emit-resolved-assets", "--run-id", args["run-id"], "--iteration", String(args.iteration)];
  if (args["svg-report"]) command.push("--svg-report", args["svg-report"]);
  if (args["schema-dir"]) command.push("--schema-dir", args["schema-dir"]);
  if (args["log-file"]) command.push("--log-file", args["log-file"]);
  const completed = await runProcess(python, command);
  let payload;
  try { payload = JSON.parse(completed.stdout); } catch { payload = null; }
  if (completed.code !== 0 || payload?.status !== "ok") {
    const detail = payload?.error;
    throw new BuildError(detail?.message ?? `asset validation failed: ${completed.stderr.trim()}`, { exitCode: detail?.exit_code ?? 5, category: detail?.category ?? "asset_validation", target: detail?.path ?? args["asset-manifest"] });
  }
  return payload.outputs;
}

async function validateSummary(summaryPath, python, args) {
  const command = [path.join(SCRIPT_DIR, "validate_spec.py"), "--build-summary", summaryPath];
  if (args["schema-dir"]) command.push("--schema-dir", args["schema-dir"]);
  const completed = await runProcess(python, command);
  if (completed.code !== 0) throw new BuildError("generated build summary failed Schema validation", { exitCode: 6, category: "summary_invalid", target: summaryPath });
}

export async function buildPresentation(args) {
  const inputs = [args.layout, args["asset-manifest"], args["asset-dir"], args["svg-report"]];
  const outputs = [args.output, args["build-summary"]];
  const iterationDir = await enforceIterationBoundary(args["iteration-dir"], inputs, outputs, [args["log-file"]]);
  args.__logAuthorized = true;
  await logEvent(args["log-file"], { level: "info", component: COMPONENT, event: "started", message: "PPT build started", runId: args["run-id"], iteration: args.iteration });
  const layout = await readJson(args.layout);
  if (layout.metadata?.iteration !== args.iteration) throw new BuildError("CLI iteration does not match layout metadata", { category: "iteration_mismatch", target: "--iteration" });
  const python = args.python ?? process.env.IVT_PYTHON ?? "python";
  const resolved = await validateAndResolveAssets(args, python);
  if (await sha256File(args.layout) !== resolved.layout_sha256 || await sha256File(args["asset-manifest"]) !== resolved.manifest_sha256) {
    throw new BuildError("layout or asset manifest changed after validation", { exitCode: 9, category: "hash_conflict" });
  }

  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: "IVT_CUSTOM", width: layout.slide.width_in, height: layout.slide.height_in });
  pptx.layout = "IVT_CUSTOM";
  pptx.author = "Content to Editable PPT Skill";
  pptx.company = "";
  pptx.subject = "Deterministic editable PowerPoint build";
  pptx.title = layout.metadata.topic;
  pptx.revision = "1";
  const slide = pptx.addSlide();
  const assets = new Map(resolved.resolved_assets.map((asset) => [asset.id, asset]));
  const { ordered, elementMap, usedAssets, typography, connections, expectedIds, builtIds, missing, unexpected } = await buildSlideIntoPresentation({ pptx, slide, layout, assets });

  await mkdir(path.dirname(args.output), { recursive: true });
  const temporary = await mkdtemp(path.join(iterationDir, ".build-slide-"));
  const stagedPptx = path.join(temporary, path.basename(args.output));
  const stagedSummary = path.join(temporary, path.basename(args["build-summary"]));
  let outputCommitted = false;
  try {
    const raw = await pptx.write({ outputType: "nodebuffer", compression: true });
    const pptxBytes = await normalizePptx(Buffer.from(raw));
    await writeFile(stagedPptx, pptxBytes);
    const summary = {
      schema_version: "1.3",
      run_id: args["run-id"],
      iteration: args.iteration,
      hashes: { layout_sha256: resolved.layout_sha256, asset_manifest_sha256: resolved.manifest_sha256, output_pptx_sha256: sha256Bytes(pptxBytes) },
      output_pptx: path.relative(iterationDir, args.output).split(path.sep).join("/"),
      expected_element_count: expectedIds.length,
      built_element_count: builtIds.size,
      missing_element_ids: missing,
      unexpected_element_ids: unexpected,
      build_order: ordered.map(({ element }) => element.id),
      element_map: elementMap.sort((left, right) => expectedIds.indexOf(left.element_id) - expectedIds.indexOf(right.element_id)),
      assets: [...usedAssets.values()].sort((left, right) => left.asset_id.localeCompare(right.asset_id)),
      typography,
      connections,
      warnings: [],
    };
    await writeFile(stagedSummary, `${JSON.stringify(summary, null, 2)}\n`, "utf8");
    await validateSummary(stagedSummary, python, args);
    await rename(stagedPptx, args.output);
    outputCommitted = true;
    await rename(stagedSummary, args["build-summary"]);
    return summary;
  } catch (error) {
    if (outputCommitted) await unlink(args.output).catch(() => {});
    await unlink(args["build-summary"]).catch(() => {});
    throw error;
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
}

async function main() {
  let args;
  try {
    args = parseArgs(process.argv.slice(2));
    const summary = await buildPresentation(args);
    const outputs = { pptx: path.resolve(args.output), build_summary: path.resolve(args["build-summary"]), pptx_sha256: summary.hashes.output_pptx_sha256, element_count: summary.built_element_count, build_order: summary.build_order };
    await logEvent(args["log-file"], { level: "info", component: COMPONENT, event: "completed", message: "PPT build completed", runId: args["run-id"], iteration: args.iteration, data: { exit_code: 0, element_count: summary.built_element_count } });
    console.log(JSON.stringify(success(COMPONENT, outputs, args["run-id"], args.iteration)));
    return 0;
  } catch (error) {
    const runId = args?.["run-id"] ?? "unknown";
    const iteration = args?.iteration ?? null;
    if (args?.__logAuthorized) await logEvent(args["log-file"], { level: "error", component: COMPONENT, event: "failed", message: error.message, runId, iteration, data: { exit_code: error instanceof BuildError ? error.exitCode : 70 } }).catch(() => {});
    const payload = failure(COMPONENT, error, runId, iteration);
    console.log(JSON.stringify(payload));
    return payload.error.exit_code;
  }
}

if (path.resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url)) process.exitCode = await main();
