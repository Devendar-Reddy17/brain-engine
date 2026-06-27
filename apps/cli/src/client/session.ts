import { BrainConfigShape } from "../config/defaultConfig";
import { configExists, loadConfig } from "../config/configLoader";
import { ensureDaemon } from "../daemon/daemonManager";
import { ConfigMissingError } from "../utils/errors";
import { detectRepoRoot } from "../utils/paths";
import { BrainDaemonClient } from "./brainDaemonClient";

export interface Session {
  repoRoot: string;
  config: BrainConfigShape;
  client: BrainDaemonClient;
}

/** Resolve repo root + config and ensure the daemon is running. */
export async function openSession(options: { requireConfig?: boolean } = {}): Promise<Session> {
  const repoRoot = detectRepoRoot();
  if (options.requireConfig && !configExists(repoRoot)) {
    throw new ConfigMissingError(
      "No .brain/config.yml found.",
      "Run `brain config` first to initialize this repository.",
    );
  }
  const config = loadConfig(repoRoot);
  const client = await ensureDaemon(repoRoot, config);
  return { repoRoot, config, client };
}
