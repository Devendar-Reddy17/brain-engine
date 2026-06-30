import { Command } from "commander";

import { getReasoningAiProvider } from "../ai/aiProvider";
import { buildReviewPrompt } from "../ai/promptBuilder";
import { openSession } from "../client/session";
import { logger } from "../utils/logger";
import { logSendingTokens, printTokenSavings } from "../utils/tokenSavings";

export function registerReviewCommand(program: Command): void {
  program
    .command("review")
    .description("Review the current git diff with the AI provider")
    .option("--diff", "Review the current working-tree git diff", false)
    .action(async (opts: { diff?: boolean }) => {
      const { config, client } = await openSession({ requireConfig: true });

      // `--diff` is the supported mode today; review always targets the working-tree diff.
      void opts.diff;
      const prompt = "Review the current changes for risks, missing tests, bugs, and improvements.";
      const ctx = await client.context({ prompt, intent: "review", includeFullDiff: true });

      if (!ctx.gitDiffSummary) {
        logger.warn("No uncommitted changes detected to review.");
        return;
      }

      printTokenSavings(ctx.tokenSavings);
      logSendingTokens(ctx.tokenSavings);

      const ai = getReasoningAiProvider(config);
      logger.brain(`Reviewing changes with ${ai.model}...`);
      const review = await ai.complete({ messages: buildReviewPrompt(ctx) });

      logger.heading("Code Review");
      process.stdout.write(`${review.trim()}\n`);
    });
}
