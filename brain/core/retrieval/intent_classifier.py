"""Classify the user's intent and extract keywords from a prompt.

Pure heuristics (no AI). Intent drives retrieval weighting (e.g. include tests
for test creation, include diff for review). Keyword extraction pulls likely
identifiers, file names, routes, and quoted/domain terms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from brain.types.brain_types import Intent

_INTENT_PATTERNS: list[tuple[Intent, tuple[str, ...]]] = [
    (Intent.REVIEW, ("review", "code review", "risk", "looks good", "feedback on")),
    (Intent.BUG_FIX, ("bug", "fix", "error", "exception", "npe", "fails", "broken", "crash", "stack trace")),
    (Intent.TEST_CREATION, ("test", "unit test", "junit", "coverage", "write a test", "add tests")),
    (Intent.REFACTOR, ("refactor", "clean up", "rename", "extract", "simplify", "restructure")),
    (Intent.CODE_EDIT, ("add", "implement", "create", "change", "update", "modify", "validation", "endpoint")),
    (Intent.ARCHITECTURE_EXPLANATION, ("architecture", "overview", "how does", "explain the flow", "design", "structure")),
]

_IDENTIFIER_RE = re.compile(r"\b([A-Z][A-Za-z0-9]+(?:[A-Z][A-Za-z0-9]+)*|[a-z][a-zA-Z0-9]*[A-Z][A-Za-z0-9]*)\b")
_FILE_RE = re.compile(r"\b[\w./-]+\.[A-Za-z]{1,5}\b")
_PATH_RE = re.compile(r"/[A-Za-z0-9_{}/-]+")
_QUOTED_RE = re.compile(r"[\"'`]([^\"'`]+)[\"'`]")

_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "your",
    "where", "what", "how", "why", "is", "are", "to", "in", "of", "a", "an",
    "add", "fix", "explain", "implement", "please", "can", "you", "code",
    # Generic code/HTTP terms that match too many chunks to be useful for
    # content LIKE search.  These are still used for exact symbol-name lookup
    # (a symbol literally named ``get`` is a real match).
    "get", "post", "put", "delete", "api", "route", "endpoint", "handler",
    "method", "class", "file", "present", "located", "defined", "show",
    "find", "list", "all", "which", "number",
    "controller", "service", "implementation", "impl", "dto", "jpa",
    "repository", "repo", "backing", "returns", "return",
}


@dataclass
class IntentResult:
    intent: Intent
    keywords: list[str] = field(default_factory=list)
    file_hints: list[str] = field(default_factory=list)


def classify(prompt: str) -> IntentResult:
    lowered = prompt.lower()

    intent = Intent.QUESTION
    for candidate, patterns in _INTENT_PATTERNS:
        if any(_matches_pattern(lowered, p) for p in patterns):
            intent = candidate
            break

    identifiers = [i for i in _dedup(_IDENTIFIER_RE.findall(prompt)) if not is_noise_term(i)]
    file_hints = _dedup(_FILE_RE.findall(prompt))
    paths = _dedup(_PATH_RE.findall(prompt))
    quoted = [m for m in _QUOTED_RE.findall(prompt)]

    words = [w for w in re.findall(r"[A-Za-z0-9_]+", lowered) if w not in _STOPWORDS and len(w) > 2]
    # All extracted patterns merge into one unified keywords bag — no
    # domain-specific separation.  Paths, identifiers, quoted terms, and
    # plain words are all just signals to search for.
    keywords = _dedup([*identifiers, *paths, *quoted, *words])

    return IntentResult(
        intent=intent,
        keywords=keywords,
        file_hints=file_hints,
    )


def is_noise_term(term: str) -> bool:
    """True if *term* is too generic to be useful for content LIKE search."""

    return term.lower() in _STOPWORDS


def _matches_pattern(text: str, pattern: str) -> bool:
    if re.fullmatch(r"[a-z0-9]+", pattern):
        return re.search(rf"\b{re.escape(pattern)}\b", text) is not None
    return pattern in text


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if key and key.lower() not in seen:
            seen.add(key.lower())
            out.append(key)
    return out
