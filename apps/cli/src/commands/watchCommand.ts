import { Command } from "commander";

import { openSession } from "../client/session";
import { logger } from "../utils/logger";

export function registerWatchCommand(program: Command): void {
  program
    .command("watch")
    .description("Start background watch mode (incremental re-indexing of changed files)")
    .option("--stop", "Stop watch mode instead of starting it", false)
    .action(async (opts: { stop?: boolean }) => {
      const { client } = await openSession({ requireConfig: true });
      if (opts.stop) {
        await client.stopWatch();
        logger.success("Watch mode stopped.");
        return;
      }
      await client.startWatch();
      logger.success("Watch mode active. The daemon will re-index only changed files.");
      logger.info("The daemon runs in the background; you can keep working normally.");
    });
}
