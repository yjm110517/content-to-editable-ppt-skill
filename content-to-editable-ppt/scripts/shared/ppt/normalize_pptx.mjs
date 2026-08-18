import JSZip from "jszip";
import { BuildError } from "../../build_common.mjs";

const FIXED_DATE = new Date("1980-01-01T00:00:00.000Z");

export async function normalizePptx(buffer, requiredSlides = 1) {
  const source = await JSZip.loadAsync(buffer); const normalized = new JSZip();
  for (const name of Object.keys(source.files).sort()) {
    const entry = source.files[name];
    if (entry.dir) { normalized.file(name, "", { dir: true, date: FIXED_DATE, unixPermissions: 0o755 }); continue; }
    let content = await entry.async("nodebuffer");
    if (name === "docProps/core.xml") {
      let xml = content.toString("utf8");
      xml = xml.replace(/<dcterms:created[^>]*>.*?<\/dcterms:created>/s, '<dcterms:created xsi:type="dcterms:W3CDTF">1980-01-01T00:00:00Z</dcterms:created>');
      xml = xml.replace(/<dcterms:modified[^>]*>.*?<\/dcterms:modified>/s, '<dcterms:modified xsi:type="dcterms:W3CDTF">1980-01-01T00:00:00Z</dcterms:modified>');
      content = Buffer.from(xml, "utf8");
    }
    normalized.file(name, content, { date: FIXED_DATE, binary: true, unixPermissions: 0o644 });
  }
  const result = await normalized.generateAsync({ type: "nodebuffer", platform: "UNIX", compression: "DEFLATE", compressionOptions: { level: 9 }, streamFiles: false });
  const check = await JSZip.loadAsync(result);
  for (const required of ["[Content_Types].xml", "ppt/presentation.xml", "docProps/core.xml"]) if (!check.file(required)) throw new BuildError("PPTX package is missing a required part", { exitCode: 6, category: "pptx_integrity", target: required });
  for (let index = 1; index <= requiredSlides; index += 1) if (!check.file(`ppt/slides/slide${index}.xml`)) throw new BuildError("PPTX package is missing a slide", { exitCode: 6, category: "pptx_integrity", target: `slide${index}` });
  return result;
}
