import chalk from "chalk";
import type { TokenSavings } from "@local-code-brain/shared";

import { logger } from "./logger";

function fmt(n: number): string {
  return n.toLocaleString("en-US");
}

/** Compact, uncluttered token-savings summary block (CLI output). */
export function printTokenSavings(ts: TokenSavings): void {
  logger.heading("Token Savings");
  process.stdout.write(`${chalk.dim("-------------")}\n`);
  process.stdout.write(`Full Repository: ${fmt(ts.repoTokens)} tokens\n`);
  process.stdout.write(`Packed Context: ${fmt(ts.contextTokens)} tokens\n`);
  process.stdout.write(`Reduction: ${ts.reductionPercentage}%\n`);
}

/** Log line emitted before an AI call (ask/edit/review). */
export function logSendingTokens(ts: TokenSavings): void {
  logger.brain(
    `Sending ${fmt(ts.contextTokens)} tokens instead of estimated ${fmt(ts.repoTokens)}`,
  );
}
