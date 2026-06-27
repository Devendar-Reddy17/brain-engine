import chalk from "chalk";
import { Command } from "commander";

import { openSession } from "../client/session";
import { logger } from "../utils/logger";

export function registerStatusCommand(program: Command): void {
  program
    .command("status")
    .description("Show repo index status and freshness")
    .action(async () => {
      const { client } = await openSession({ requireConfig: true });
      const s = await client.status();

      logger.heading("Local Code Brain Status");
      logger.info(`Repo root:        ${s.repoRoot}`);
      logger.info(`Current branch:   ${s.currentBranch ?? "(unknown)"}`);
      logger.info(`Indexed files:    ${s.indexedFiles}`);
      logger.info(`Chunks:           ${s.chunks}`);
      logger.info(`Symbols:          ${s.symbols}`);
      logger.info(`Last full index:  ${s.lastFullIndexAt ?? "(never)"}`);
      logger.info(`Last incremental: ${s.lastIncrementalIndexAt ?? "(never)"}`);
      logger.info(`Pending queue:    ${s.pendingQueueSize}`);
      const freshness = s.fresh ? chalk.green("fresh") : chalk.yellow("stale");
      logger.info(`Index state:      ${freshness}`);

      if (s.stale) {
        const reason = s.staleReason ?? "Index built with outdated components.";
        process.stdout.write(
          `\n${chalk.yellow("\u26a0 Index is out of date after an upgrade.")}\n` +
            `${reason}\n` +
            `${chalk.bold("Run 'brain index' to rebuild.")}\n`,
        );
      }
    });
}
