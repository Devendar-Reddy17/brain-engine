import * as fs from "node:fs";

import { ensureBrainDirs, latestPatchPath } from "../utils/paths";

/** Persist a patch to .brain/patches/latest.patch and return its path. */
export function writeLatestPatch(repoRoot: string, patch: string): string {
  ensureBrainDirs(repoRoot);
  const file = latestPatchPath(repoRoot);
  fs.writeFileSync(file, patch, "utf-8");
  return file;
}

export function readPatch(patchPath: string): string {
  return fs.readFileSync(patchPath, "utf-8");
}
