import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";

import { BrainDaemonClient } from "../client/brainDaemonClient";
import { BrainConfigShape } from "../config/defaultConfig";
import { DaemonUnavailableError } from "../utils/errors";
import { logger } from "../utils/logger";
import { daemonLogPath } from "../utils/paths";

const READY_TIMEOUT_MS = 30_000;
const POLL_INTERVAL_MS = 500;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Locate the repo containing the Python `brain` package (monorepo root). */
function findBrainPackageRoot(startDir: string): string | null {
  let current = path.resolve(startDir);
  // eslint-disable-next-line no-constant-condition
  while (true) {
    if (fs.existsSync(path.join(current, "brain", "daemon", "main.py"))) {
      return current;
    }
    const parent = path.dirname(current);
    if (parent === current) {
      return null;
    }
    current = parent;
  }
}

/**
 * Ensure the Python daemon is running for `repoRoot`, returning a connected
 * client. Auto-starts the daemon when `daemon.auto_start` is enabled.
 */
export async function ensureDaemon(
  repoRoot: string,
  config: BrainConfigShape,
): Promise<BrainDaemonClient> {
  const { host, port, auto_start: autoStart, python_command: pythonCommand } = config.daemon;
  const client = new BrainDaemonClient(host, port);

  if (await client.isAlive()) {
    return client;
  }

  if (!autoStart) {
    throw new DaemonUnavailableError(
      `Brain daemon is not running at ${host}:${port}.`,
      `Start it with:\n  ${pythonCommand} -m brain.daemon.main --repo-root "${repoRoot}"\nor enable daemon.auto_start in .brain/config.yml.`,
    );
  }

  const packageRoot = findBrainPackageRoot(repoRoot) ?? findBrainPackageRoot(__dirname);
  if (!packageRoot) {
    throw new DaemonUnavailableError(
      "Could not locate the Python brain package (brain/daemon/main.py).",
      "Ensure the Local Code Brain installation includes the Python daemon.",
    );
  }

  logger.brain(`Starting brain daemon (${pythonCommand}) on ${host}:${port}...`);
  const logFd = fs.openSync(daemonLogPath(repoRoot), "a");
  const child = spawn(
    pythonCommand,
    ["-m", "brain.daemon.main", "--repo-root", repoRoot, "--host", host, "--port", String(port)],
    {
      cwd: packageRoot,
      detached: true,
      stdio: ["ignore", logFd, logFd],
      env: { ...process.env, PYTHONPATH: packageRoot },
    },
  );
  child.on("error", (err) => {
    logger.error(`Failed to spawn daemon: ${err.message}`);
  });
  child.unref();

  const deadline = Date.now() + READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (await client.isAlive()) {
      logger.brain("Daemon is ready.");
      return client;
    }
    await sleep(POLL_INTERVAL_MS);
  }

  throw new DaemonUnavailableError(
    "Brain daemon did not become ready in time.",
    `Check the daemon log at ${daemonLogPath(repoRoot)} and verify '${pythonCommand}' and dependencies are installed (pip install -r requirements.txt).`,
  );
}
