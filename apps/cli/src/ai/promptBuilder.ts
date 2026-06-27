import type { ContextResponse } from "@local-code-brain/shared";

import { ChatMessage } from "./aiProvider";

const ASK_SYSTEM = `You are a senior engineer answering questions about a specific repository.
You are given a compact, dependency-aware context package prepared locally.
Answer using ONLY the provided context. If the context is insufficient, say so
explicitly and state what additional files would help. Do not invent APIs.`;

const EDIT_SYSTEM = `You are a senior engineer making a precise code change in a specific repository.
You are given a compact, dependency-aware context package prepared locally.
Rules:
- Modify only relevant files.
- Preserve existing architecture and style.
- Do not invent missing APIs.
- Add or update tests when appropriate.
- Return ONLY a single unified diff (git format) and nothing else.
- Use paths relative to the repository root in the diff headers.`;

const REVIEW_SYSTEM = `You are a senior engineer performing a code review of the current git diff.
You are given the diff plus a compact, dependency-aware repository context.
Provide concise, actionable feedback grouped under: Risks, Missing Tests, Bugs,
and Improvement Suggestions. Reference files and symbols from the context.`;

function userMessage(contextMarkdown: string, instruction: string): string {
  return `${contextMarkdown}\n\n---\n\n${instruction}`;
}

export function buildAskPrompt(ctx: ContextResponse): ChatMessage[] {
  return [
    { role: "system", content: ASK_SYSTEM },
    { role: "user", content: userMessage(ctx.markdown, `Question: ${ctx.prompt}`) },
  ];
}

export function buildEditPrompt(ctx: ContextResponse): ChatMessage[] {
  return [
    { role: "system", content: EDIT_SYSTEM },
    {
      role: "user",
      content: userMessage(
        ctx.markdown,
        `Task: ${ctx.prompt}\n\nReturn ONLY a unified diff patch.`,
      ),
    },
  ];
}

export function buildReviewPrompt(ctx: ContextResponse): ChatMessage[] {
  return [
    { role: "system", content: REVIEW_SYSTEM },
    {
      role: "user",
      content: userMessage(ctx.markdown, "Review the current changes shown in the git diff above."),
    },
  ];
}
