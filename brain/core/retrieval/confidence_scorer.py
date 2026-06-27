"""Score how confident we are that the retrieved context is sufficient.

Heuristic, deterministic 0.0-1.0 score plus a human-readable reason. Considers
the strength of the top hits, whether exact symbol/file matches were found, and
how much of the keyword set was covered.
"""

from __future__ import annotations

from brain.core.retrieval.reranker import Candidate


def score(
    ranked: list[Candidate],
    *,
    keywords: list[str],
    had_exact_symbol: bool,
    had_file_match: bool,
) -> tuple[float, str]:
    if not ranked:
        return 0.1, "No relevant chunks were found; context is likely insufficient."

    value = 0.35
    reasons: list[str] = []

    top = ranked[0]
    if top.score >= 8:
        value += 0.25
        reasons.append("strong top match")
    elif top.score >= 4:
        value += 0.15
        reasons.append("moderate top match")

    if had_exact_symbol:
        value += 0.2
        reasons.append("exact symbol match found")
    if had_file_match:
        value += 0.1
        reasons.append("file path match found")

    # Keyword coverage across retrieved chunks.
    if keywords:
        covered = 0
        joined = " ".join(c.content.lower() for c in ranked[:8])
        for kw in keywords:
            if kw.lower() in joined:
                covered += 1
        coverage = covered / len(keywords)
        value += 0.1 * coverage
        if coverage >= 0.6:
            reasons.append("good keyword coverage")
        elif coverage < 0.3:
            reasons.append("low keyword coverage")

    value = round(max(0.0, min(1.0, value)), 2)
    reason = ", ".join(reasons) if reasons else "based on retrieval signals"
    qualifier = "context is likely sufficient" if value >= 0.6 else (
        "context may be incomplete" if value >= 0.4 else "context is likely insufficient"
    )
    return value, f"{qualifier} ({reason})."
