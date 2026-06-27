import * as fs from "node:fs";
import * as YAML from "yaml";

import { configPath, ensureBrainDirs } from "../utils/paths";
import { BrainConfigShape, defaultConfig } from "./defaultConfig";

function deepMerge<T>(base: T, override: Partial<T>): T {
  const result: Record<string, unknown> = { ...(base as Record<string, unknown>) };
  for (const [key, value] of Object.entries(override ?? {})) {
    const baseValue = (base as Record<string, unknown>)[key];
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      baseValue &&
      typeof baseValue === "object"
    ) {
      result[key] = deepMerge(baseValue, value as Record<string, unknown>);
    } else if (value !== undefined) {
      result[key] = value;
    }
  }
  return result as T;
}

/** Load `.brain/config.yml`, merged onto defaults. Returns defaults if absent. */
export function loadConfig(repoRoot: string): BrainConfigShape {
  const file = configPath(repoRoot);
  const base = defaultConfig();
  if (!fs.existsSync(file)) {
    return base;
  }
  const raw = YAML.parse(fs.readFileSync(file, "utf-8")) as Partial<BrainConfigShape> | null;
  if (!raw || typeof raw !== "object") {
    return base;
  }
  return deepMerge(base, raw);
}

/** Write config to `.brain/config.yml`, creating dirs. Returns the path. */
export function writeConfig(repoRoot: string, config?: BrainConfigShape): string {
  ensureBrainDirs(repoRoot);
  const file = configPath(repoRoot);
  fs.writeFileSync(file, YAML.stringify(config ?? defaultConfig()), "utf-8");
  return file;
}

export function configExists(repoRoot: string): boolean {
  return fs.existsSync(configPath(repoRoot));
}
