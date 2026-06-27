import { BrainDaemonClient } from "../client/brainDaemonClient";

export const getRepoContextInputSchema = {
  type: "object",
  properties: {
    prompt: {
      type: "string",
      description: "The task or question to build repository context for",
    },
    includeFullDiff: {
      type: "boolean",
      description: "Include the full working-tree git diff if within token budget",
    },
  },
  required: ["prompt"],
} as const;

/** Returns the compact, dependency-aware context package for a prompt. */
export async function getRepoContext(
  client: BrainDaemonClient,
  args: { prompt: string; includeFullDiff?: boolean },
): Promise<string> {
  const ctx = await client.context({
    prompt: args.prompt,
    includeFullDiff: Boolean(args.includeFullDiff),
  });
  const ts = ctx.tokenSavings;
  const header =
    `Token Savings: ${ts.contextTokens.toLocaleString()} of ~${ts.repoTokens.toLocaleString()} ` +
    `repo tokens (${ts.reductionPercentage}% reduction).\n\n`;
  return header + ctx.markdown;
}
