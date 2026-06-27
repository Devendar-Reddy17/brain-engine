#!/usr/bin/env node
import { Command } from "commander";

import { registerApplyCommand } from "./commands/applyCommand";
import { registerAskCommand } from "./commands/askCommand";
import { registerConfigCommand } from "./commands/configCommand";
import { registerContextCommand } from "./commands/contextCommand";
import { registerEditCommand } from "./commands/editCommand";
import { registerGitRefreshCommand } from "./commands/gitRefreshCommand";
import { registerIndexCommand } from "./commands/indexCommand";
import { registerReviewCommand } from "./commands/reviewCommand";
import { registerStatusCommand } from "./commands/statusCommand";
import { registerWatchCommand } from "./commands/watchCommand";
import { BrainCliError } from "./utils/errors";
import { logger } from "./utils/logger";

const program = new Command();

program
  .name("brain")
  .description("Local Code Brain - local-first repo intelligence for AI coding agents")
  .version("0.1.0");

registerConfigCommand(program);
registerIndexCommand(program);
registerStatusCommand(program);
registerContextCommand(program);
registerWatchCommand(program);
registerGitRefreshCommand(program);
registerAskCommand(program);
registerEditCommand(program);
registerReviewCommand(program);
registerApplyCommand(program);

async function main(): Promise<void> {
  try {
    await program.parseAsync(process.argv);
  } catch (err) {
    if (err instanceof BrainCliError) {
      logger.error(err.message);
      if (err.detail) {
        process.stderr.write(`${err.detail}\n`);
      }
    } else if (err instanceof Error) {
      logger.error(err.message);
    } else {
      logger.error(String(err));
    }
    process.exitCode = 1;
  }
}

void main();
