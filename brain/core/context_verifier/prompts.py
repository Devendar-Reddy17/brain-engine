"""Prompt templates for context verification."""

from __future__ import annotations

import json

from brain.core.context_verifier.types import ChunkGraph, ContextIntentResult, RetrievedChunk


INTENT_SYSTEM = """You are RepoSentinel Context Verifier. Your job is not to write code. Your job is to understand the user question and create better retrieval queries for a repo intelligence engine. Return only valid JSON."""

VERIFY_SYSTEM = """You are RepoSentinel Context Verifier. Given a user question, retrieved code chunks, and a chunk graph, decide whether the context is enough. Remove noisy chunks. Detect missing files/symbols. Generate follow-up retrieval queries if needed. Return only valid JSON."""


def intent_user(question: str) -> str:
    payload = {"question": question}
    rules = """
Expected JSON:
{
  "originalQuestion": "...",
  "rewrittenQueries": ["..."],
  "questionType": "explanation" | "implementation" | "debugging" | "review" | "unknown",
  "intensity": "low" | "medium" | "high",
  "needsMainAI": true,
  "reason": "..."
}

Rules:
- For explanation questions like "explain login flow", "how payment works", "where is X handled", set questionType to "explanation".
- For questions asking to generate/change/refactor/fix code, set needsMainAI true.
- For simple explanation questions, needsMainAI can be false.
- Generate retrieval queries that mention likely entrypoints, symbols, routes, service calls, tests, configs, and related files.
- Always keep the original user question unchanged.
- Retrieval must use the original question plus rewritten queries.
"""
    return json.dumps(payload, ensure_ascii=False) + "\n\n" + rules


def verify_user(
    *,
    question: str,
    intent: ContextIntentResult,
    chunks: list[RetrievedChunk],
    graph: ChunkGraph,
    attempt: int,
    max_attempts: int,
) -> str:
    payload = {
        "question": question,
        "intent": intent.model_dump(by_alias=True),
        "chunks": [c.model_dump(by_alias=True) for c in chunks],
        "graph": graph.model_dump(by_alias=True),
        "attempt": attempt,
        "maxAttempts": max_attempts,
    }
    rules = """
Expected JSON:
{
  "answerable": "yes" | "partial" | "no",
  "confidence": 0.0,
  "keepChunkIds": [],
  "removeChunkIds": [],
  "missingSymbols": [],
  "missingFiles": [],
  "followupQueries": [],
  "reason": "...",
  "explanation": "optional detailed explanation only if questionType is explanation and context is enough"
}

Rules:
- Do not answer implementation/code-writing questions.
- For implementation/debugging/review questions, only verify and pack context for the main AI model.
- For explanation questions, if context is enough, provide a detailed explanation using only the provided chunks.
- If direct call/import/reference edges point to a missing symbol or unresolved node, include it in missingSymbols or followupQueries.
- If chunks are only loosely keyword-related but not part of the observed graph or question intent, mark them for removal.
- Do not remove entrypoint chunks unless clearly irrelevant.
- Prefer "partial" instead of "yes" when important related files are referenced but not included.
- Stop asking for follow-up queries if attempt equals maxAttempts.
"""
    return json.dumps(payload, ensure_ascii=False) + "\n\n" + rules

