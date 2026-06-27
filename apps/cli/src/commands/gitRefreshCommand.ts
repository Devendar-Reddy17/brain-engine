import { Command } from "commander";

import { openSession } from "../client/session";
import { logger } from "../utils/logger";

export function registerGitRefreshCommand(program: Command): void {
  program
    .command("git-refresh")
    .description("Reconcile files changed by git operations and enqueue them for re-indexing")
    .action(async () => {
      const { client } = await openSession({ requireConfig: true });
      const res = await client.gitRefresh();
      logger.success(`Enqueued ${res.enqueued} changed file(s) for re-indexing.`);
      if (res.files.length > 0) {
        for (const f of res.files.slice(0, 20)) {
          logger.info(`  ${f}`);
        }
        if (res.files.length > 20) {
          logger.info(`  ...and ${res.files.length - 20} more`);
        }
      }
    });
}
