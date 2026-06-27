import type { LocalQueryResult } from "@local-code-brain/shared";

import { BrainDaemonClient } from "../client/brainDaemonClient";

export const askRepoInputSchema = {
  type: "object",
  properties: {
    prompt: { type: "string", description: "A question about the repository" },
  },
  required: ["prompt"],
} as const;

/**
 * Answers a repository question via the daemon's single `/ask` entry point.
 *
 * - For `local` results the daemon answered deterministically from the index;
 *   we return the structured answer directly (no AI framing needed).
 * - For `ai_required` results the daemon supplies a precise, fresh context
 *   package; the calling AI tool (e.g. Claude/Cursor) performs the generation.
 */
export async function askRepo(client: BrainDaemonClient, args: { prompt: string }): Promise<string> {
  const res = await client.ask({ question: args.prompt });

  if (res.executionPath === "local" && res.result) {
    return formatLocalResult(args.prompt, res.result);
  }

  const ctx = res.context;
  if (!ctx) {
    return `No answer available for: ${args.prompt}`;
  }
  return (
    `Use ONLY the following repository context to answer the question.\n` +
    `Question: ${args.prompt}\n\n` +
    ctx.markdown
  );
}

function formatLocalResult(prompt: string, result: LocalQueryResult): string {
  const lines: string[] = [];
  lines.push(`Question: ${prompt}`);
  lines.push("Answered locally from the Brain index (no AI required).");
  lines.push("");
  if (result.staleWarning) {
    lines.push(`WARNING: ${result.staleWarning}`);
    lines.push("");
  }
  lines.push(`${result.title}: ${result.count}`);
  lines.push("");
  for (const item of result.items) {
    const loc = item.filePath
      ? ` (${item.filePath}${item.startLine ? `:${item.startLine}` : ""})`
      : "";
    lines.push(`- ${item.name}${loc}`);
  }
  return lines.join("\n");
}
