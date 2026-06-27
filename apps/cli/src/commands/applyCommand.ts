import * as fs from "node:fs";
import * as path from "node:path";

import { Command } from "commander";

import { openSession } from "../client/session";
import { applyPatch } from "../patch/patchApply";
import { summarizePatch } from "../patch/patchPreview";
import { readPatch } from "../patch/patchWriter";
import { BrainCliError } from "../utils/errors";
import { logger } from "../utils/logger";
import { latestPatchPath } from "../utils/paths";

export function registerApplyCommand(program: Command): void {
  program
    .command("apply")
    .description("Apply a generated patch safely, then re-index changed files")
    .argument("[patch-file]", "Patch file to apply (defaults to .brain/patches/latest.patch)")
    .option("--no-tests", "Skip running tests even if configured")
    .action(async (patchFileArg: string | undefined, opts: { tests?: boolean }) => {
      const { repoRoot, config, client } = await openSession({ requireConfig: true });

      const patchFile = path.resolve(repoRoot, patchFileArg ?? latestPatchPath(repoRoot));
      if (!fs.existsSync(patchFile)) {
        throw new BrainCliError(
          `Patch file not found: ${patchFile}`,
          "Run `brain edit \"<prompt>\"` first to generate a patch.",
        );
      }

      const patch = readPatch(patchFile);
      const stats = summarizePatch(patch);
      logger.brain(`Applying patch: ${stats.files.length} file(s), +${stats.additions}/-${stats.deletions}`);

      const runTests =
        opts.tests !== false && config.apply.run_tests_after_apply && Boolean(config.apply.test_command);

      const result = applyPatch(repoRoot, patch, patchFile, {
        runTests,
        testCommand: config.apply.test_command,
      });

      logger.success(`Applied patch to ${result.changedFiles.length} file(s).`);

      if (result.testsRun) {
        if (result.testsPassed) {
          logger.success("Tests passed.");
        } else {
          logger.warn("Tests failed after apply:");
          if (result.testOutput) {
            process.stderr.write(`${result.testOutput}\n`);
          }
        }
      }

      // Enqueue changed files for incremental re-indexing.
      await client.enqueueChanges(result.changedFiles, "modified");
      logger.brain(`Enqueued ${result.changedFiles.length} changed file(s) for re-indexing.`);
    });
}
