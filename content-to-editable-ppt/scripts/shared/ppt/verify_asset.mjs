import { stat } from "node:fs/promises";
import { BuildError, sha256File } from "../../build_common.mjs";

export async function verifyAsset(asset) {
  try {
    const fileStat = await stat(asset.path);
    if (fileStat.size !== asset.size_bytes || await sha256File(asset.path) !== asset.sha256) throw new BuildError("asset changed after security validation", { exitCode: 9, category: "hash_conflict", target: asset.id });
  } catch (error) {
    if (error instanceof BuildError) throw error;
    throw new BuildError("validated asset became unreadable", { exitCode: 9, category: "hash_conflict", target: asset.id });
  }
}
