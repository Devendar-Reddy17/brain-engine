import { BrainCliError } from "../utils/errors";

const FENCE_RE = /```(?:diff|patch)?\s*\n([\s\S]*?)```/g;
const DIFF_HINT_RE = /^(diff --git |--- |\+\+\+ |@@ )/m;

/**
 * Extract a unified diff from an AI response. Accepts either a fenced
 * ```diff block or a raw diff body. Throws if no diff-like content is found.
 */
export function extractPatch(aiResponse: string): string {
  const candidates: string[] = [];

  let match: RegExpExecArray | null;
  while ((match = FENCE_RE.exec(aiResponse)) !== null) {
    candidates.push(match[1]);
  }
  if (candidates.length === 0) {
    candidates.push(aiResponse);
  }

  for (const candidate of candidates) {
    const trimmed = candidate.trim();
    if (DIFF_HINT_RE.test(trimmed)) {
      return normalize(trimmed);
    }
  }

  throw new BrainCliError(
    "The AI response did not contain a valid unified diff patch.",
    "Re-run `brain edit` or refine the prompt. The model must return a git-style diff.",
  );
}

function normalize(patch: string): string {
  // Ensure trailing newline so `git apply` / patch tools are happy.
  return patch.endsWith("\n") ? patch : `${patch}\n`;
}
