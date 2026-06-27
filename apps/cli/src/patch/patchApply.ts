import { execFileSync, execSync } from "node:child_process";
import * as path from "node:path";

import { BrainCliError, PatchSafetyError } from "../utils/errors";
import { isWithin } from "../utils/paths";

const PATH_HEADER_RE = /^(?:\+\+\+ b\/|--- a\/|diff --git a\/)(.+?)(?:\s+b\/.+)?$/;

/** Extract repo-relative file paths referenced by a unified diff. */
export function extractPatchPaths(patch: string): string[] {
  const paths = new Set<string>();
  for (const raw of patch.split("\n")) {
    const line = raw.trimEnd();
    const m = PATH_HEADER_RE.exec(line);
    if (!m) continue;
    let p = m[1].trim();
    if (p === "/dev/null") continue;
    // `diff --git a/x b/x` capture may include the ` b/x` tail; split defensively.
    p = p.split(/\s+b\//)[0].replace(/^a\//, "").replace(/^b\//, "");
    if (p) paths.add(p);
  }
  return [...paths];
}

/** Throw if any patched path is absolute or escapes the repo root. */
export function assertPatchPathsSafe(repoRoot: string, patch: string): string[] {
  const paths = extractPatchPaths(patch);
  if (paths.length === 0) {
    throw new PatchSafetyError("Patch does not reference any files; refusing to apply.");
  }
  for (const p of paths) {
    if (path.isAbsolute(p)) {
      throw new PatchSafetyError(`Patch references an absolute path: ${p}`);
    }
    const target = path.resolve(repoRoot, p);
    if (!isWithin(repoRoot, target)) {
      throw new PatchSafetyError(`Patch path escapes the repository root: ${p}`);
    }
  }
  return paths;
}

export interface ApplyResult {
  changedFiles: string[];
  testsRun: boolean;
  testsPassed: boolean | null;
  testOutput: string | null;
}

/** Apply a patch file with `git apply`, after verifying path safety. */
export function applyPatch(
  repoRoot: string,
  patch: string,
  patchFile: string,
  options: { runTests?: boolean; testCommand?: string } = {},
): ApplyResult {
  const changedFiles = assertPatchPathsSafe(repoRoot, patch);

  try {
    execFileSync("git", ["apply", "--whitespace=nowarn", patchFile], {
      cwd: repoRoot,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err);
    throw new BrainCliError(
      "Failed to apply patch with `git apply`.",
      `${detail}\nThe patch may not match the current files. Re-run \`brain edit\` to regenerate.`,
    );
  }

  let testsRun = false;
  let testsPassed: boolean | null = null;
  let testOutput: string | null = null;
  if (options.runTests && options.testCommand) {
    testsRun = true;
    try {
      testOutput = execSync(options.testCommand, { cwd: repoRoot, stdio: ["ignore", "pipe", "pipe"] }).toString();
      testsPassed = true;
    } catch (err) {
      testsPassed = false;
      testOutput = err instanceof Error ? err.message : String(err);
    }
  }

  return { changedFiles, testsRun, testsPassed, testOutput };
}
