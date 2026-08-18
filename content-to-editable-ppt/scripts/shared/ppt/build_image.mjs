import { BuildError } from "../../build_common.mjs";
import { basePosition } from "./apply_text_layout.mjs";
import { verifyAsset } from "./verify_asset.mjs";

export async function buildImage(slide, element, assets, usedAssets) {
  const asset = assets.get(element.asset_id);
  if (!asset) throw new BuildError("unknown asset id", { category: "unknown_asset", target: element.asset_id });
  await verifyAsset(asset);
  const options = { ...basePosition(element, `ivt:${element.id}`), path: asset.path, altText: element.alt_text ?? element.asset_id, rounding: element.rounding ?? false };
  if (element.fit !== "stretch") options.sizing = { type: element.fit, w: element.w, h: element.h };
  slide.addImage(options);
  usedAssets.set(asset.id, { asset_id: asset.id, type: asset.type, sha256: asset.sha256, source_input_sha256: asset.sha256 });
}
