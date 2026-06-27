import { BrainDaemonClient } from "../client/brainDaemonClient";

export const reviewDiffInputSchema = {
  type: "object",
  properties: {},
} as const;

/**
 * Returns repository context plus the full current git diff, framed for code
 * review. The calling AI tool performs the review generation.
 */
export async function reviewDiff(client: BrainDaemonClient): Promise<string> {
  const ctx = await client.context({
    prompt: "Review the current changes for risks, missing tests, bugs, and improvements.",
    intent: "review",
    includeFullDiff: true,
  });
  if (!ctx.gitDiffSummary) {
    return "No uncommitted changes were detected to review.";
  }
  return (
    `Review the current changes shown in the git diff using the repository context below.\n\n` +
    ctx.markdown
  );
}
