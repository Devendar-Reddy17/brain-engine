import { Command } from "commander";
import chalk from "chalk";

import { getAiProvider, isAiProviderEnabled } from "../ai/aiProvider";
import { buildAskPrompt } from "../ai/promptBuilder";
import { openSession } from "../client/session";
import { logger } from "../utils/logger";
import { logSendingTokens, printTokenSavings } from "../utils/tokenSavings";
import { formatExecutionPath, formatLocalResult } from "./askFormat";

export function registerAskCommand(program: Command): void {
  program
    .command("ask")
    .description("Answer a question about the repository (local-first; uses AI only when needed)")
    .argument("<prompt>", "The question to ask about the repository")
    .action(async (prompt: string) => {
      const { config, client } = await openSession({ requireConfig: true });

      // /ask is the single public entry point; the daemon's QueryPlanner
      // decides whether the answer is produced locally or requires AI.
      const res = await client.ask({ question: prompt });

      if (res.executionPath === "local" && res.result) {
        printExecution("local");
        const lines = formatLocalResult(res.result);
        for (const line of lines) {
          const styled = line.startsWith("! ") ? chalk.yellow(line) : line;
          process.stdout.write(`${styled}\n`);
        }
        return;
      }

      printExecution("ai_required");
      const ctx = res.context;
      if (!ctx) {
        logger.error("Daemon returned no context for AI reasoning.");
        return;
      }
      printTokenSavings(ctx.tokenSavings);

      if (ctx.verifierExplanation && ctx.verifierNeedsMainAi === false) {
        logger.heading("Verifier Answer");
        process.stdout.write(`${ctx.verifierExplanation.trim()}\n\n`);
        logger.heading("Verified Context");
        process.stdout.write(`${ctx.markdown}\n`);
        return;
      }

      // Show the actual content being sent so the user can verify the packed context.
      logSendingTokens(ctx.tokenSavings);
      const messages = buildAskPrompt(ctx);
      logger.heading("Context Preview");
      for (const msg of messages) {
        process.stdout.write(`${chalk.dim(`--- ${msg.role} ---`)}\n`);
        process.stdout.write(`${msg.content}\n\n`);
      }

      if (!isAiProviderEnabled(config)) {
        logger.warn("AI provider is disabled; returning compact context only.");
        logger.info(
          "For standalone CLI explanations without local installs, configure ai.provider: hosted and point ai.base_url at your model gateway. MCP clients can use the context above with their built-in AI.",
        );
        return;
      }

      const ai = getAiProvider(config);
      logger.brain(`Asking ${ai.model}...`);
      const answer = await ai.complete({ messages });

      logger.heading("Answer");
      process.stdout.write(`${answer.trim()}\n`);
    });
}

function printExecution(path: "local" | "ai_required"): void {
  logger.heading("Execution");
  process.stdout.write(`${chalk.green("\u2714")} ${formatExecutionPath(path)}\n\n`);
}
