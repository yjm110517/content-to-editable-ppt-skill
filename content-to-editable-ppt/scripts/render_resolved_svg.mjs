import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { Resvg } from "@resvg/resvg-js";

const [input, output] = process.argv.slice(2);
if (!input || !output) throw new Error("usage: render_resolved_svg.mjs <input.svg> <output.png>");
const source = await readFile(input);
const rendered = new Resvg(source, { fitTo: { mode: "width", value: 96 } }).render().asPng();
await writeFile(output, rendered);
const version = createRequire(import.meta.url)("@resvg/resvg-js/package.json").version;
const sha256 = (value) => createHash("sha256").update(value).digest("hex");
console.log(JSON.stringify({ source_sha256: sha256(source), rendered_png_sha256: sha256(rendered), resvg_version: version, node_version: process.version, platform: `${process.platform}-${process.arch}` }));
