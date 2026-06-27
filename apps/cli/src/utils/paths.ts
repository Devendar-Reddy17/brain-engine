import { execSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";

const MARKERS = [".git", ".brain", "pom.xml", "build.gradle", "build.gradle.kts", "package.json"];

/** Walk up from `start` to find a repo root by well-known markers. */
export function detectRepoRoot(start: string = process.cwd()): string {
  let current = path.resolve(start);
  // eslint-disable-next-line no-constant-condition
  while (true) {
    for (const marker of MARKERS) {
      if (fs.existsSync(path.join(current, marker))) {
        return current;
      }
    }
    const parent = path.dirname(current);
    if (parent === current) {
      return path.resolve(start);
    }
    current = parent;
  }
}

export function brainDir(repoRoot: string): string {
  return path.join(repoRoot, ".brain");
}

export function configPath(repoRoot: string): string {
  return path.join(brainDir(repoRoot), "config.yml");
}

export function patchesDir(repoRoot: string): string {
  return path.join(brainDir(repoRoot), "patches");
}

export function latestPatchPath(repoRoot: string): string {
  return path.join(patchesDir(repoRoot), "latest.patch");
}

export function daemonPidPath(repoRoot: string): string {
  return path.join(brainDir(repoRoot), "daemon.pid");
}

export function daemonLogPath(repoRoot: string): string {
  return path.join(brainDir(repoRoot), "daemon.log");
}

export function ensureBrainDirs(repoRoot: string): void {
  fs.mkdirSync(patchesDir(repoRoot), { recursive: true });
}

/** True if `child` resolves inside `parent` (used for patch path safety). */
export function isWithin(parent: string, child: string): boolean {
  const rel = path.relative(path.resolve(parent), path.resolve(child));
  return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}

/** Best-effort `git` branch lookup for status display. */
export function currentBranch(repoRoot: string): string | null {
  try {
    return execSync("git rev-parse --abbrev-ref HEAD", {
      cwd: repoRoot,
      stdio: ["ignore", "pipe", "ignore"],
    })
      .toString()
      .trim();
  } catch {
    return null;
  }
}
