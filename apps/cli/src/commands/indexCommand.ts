import { Command } from "commander";

import { openSession } from "../client/session";
import { logger } from "../utils/logger";

export function registerIndexCommand(program: Command): void {
  program
    .command("index")
    .description("Run a full index of the repository (no code is sent to the cloud)")
    .action(async () => {
      const { client } = await openSession({ requireConfig: true });
      logger.brain("Indexing repository locally...");
      const result = await client.index(true);
      logger.success(
        `Indexed ${result.filesIndexed} file(s) (${result.filesSkipped} unchanged) ` +
          `in ${result.durationMs}ms`,
      );
      if (result.forced) {
        logger.info("Index was stale — every file was rebuilt from current code.");
      }
      logger.info(
        `This run:  ${result.filesIndexed} file(s) | ${result.chunksCreated} chunk(s) | ` +
          `${result.symbolsExtracted} symbol(s)`,
      );
      logger.info(
        `In index:  ${result.totalFiles} file(s) | ${result.totalChunks} chunk(s) | ` +
          `${result.totalSymbols} symbol(s)`,
      );
    });
}
