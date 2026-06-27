import { Command } from "commander";

import { configExists, writeConfig } from "../config/configLoader";
import { logger } from "../utils/logger";
import { configPath, detectRepoRoot } from "../utils/paths";

export function registerConfigCommand(program: Command): void {
  program
    .command("config")
    .description("Generate or update .brain/config.yml")
    .option("--force", "Overwrite an existing config with defaults", false)
    .action((opts: { force?: boolean }) => {
      const repoRoot = detectRepoRoot();
      const exists = configExists(repoRoot);
      if (exists && !opts.force) {
        logger.warn(`Config already exists at ${configPath(repoRoot)}`);
        logger.info("Use `brain config --force` to reset it to defaults.");
        return;
      }
      const file = writeConfig(repoRoot);
      logger.success(`${exists ? "Reset" : "Created"} config at ${file}`);
    });
}
