import { Command } from "commander";

import { getAiProvider } from "../ai/aiProvider";
import { buildEditPrompt } from "../ai/promptBuilder";
import { extractPatch } from "../ai/patchExtractor";
import { openSession } from "../client/session";
import { printPatchPreview } from "../patch/patchPreview";
import { writeLatestPatch } from "../patch/patchWriter";
import { logger } from "../utils/logger";
import { logSendingTokens, printTokenSavings } from "../utils/tokenSavings";

export function registerEditCommand(program: Command): void {
  program
    .command("edit")
    .description("Retrieve context and ask the AI for a unified diff patch (does NOT auto-apply)")
    .argument("<prompt>", "The code-change request")
    .action(async (prompt: string) => {
      const { repoRoot, config, client } = await openSession({ requireConfig: true });

      const ctx = await client.context({ prompt, includeFullDiff: true });
      printTokenSavings(ctx.tokenSavings);
      logSendingTokens(ctx.tokenSavings);

      const ai = getAiProvider(config);
      logger.brain(`Requesting patch from ${ai.model}...`);
      const response = await ai.complete({ messages: buildEditPrompt(ctx) });

      const patch = extractPatch(response);
      const file = writeLatestPatch(repoRoot, patch);

      logger.heading("Proposed Patch");
      printPatchPreview(patch);

      logger.success(`Patch saved to ${file}`);
      logger.info(`Review it, then apply with:\n  brain apply ${file}`);
    });
}
