"""Rerank retrieval candidates per the spec's priority rules.

Priority (high -> low):
  * exact symbol match
  * file-path match
  * recently changed files
  * tests/config/routes (intent dependent)
  * graph-neighbour chunks (medium)
  * generic vector matches (lower)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from brain.core.retrieval.intent_classifier import is_partial_symbol_signal
from brain.types.brain_types import Intent


@dataclass
class Candidate:
    chunk_id: str
    file_path: str
    symbol_name: str | None
    symbol_type: str | None
    start_line: int
    end_line: int
    content: str
    source: str  # "symbol" | "lexical" | "vector" | "graph"
    base_score: float = 0.0
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        return "; ".join(self.reasons) if self.reasons else self.source


_SOURCE_WEIGHTS = {
    "route_exact": 8.0,
    "file_hint": 6.0,
    "query_alias": 6.0,
    "call_target": 7.0,
    "feature_context": 6.5,
    "symbol": 5.0,
    "symbol_partial": 3.5,
    "lexical": 2.0,
    "vector": 1.0,
    "graph": 2.5,
}


def rerank(
    candidates: list[Candidate],
    *,
    intent: Intent,
    keywords: list[str],
    file_hints: list[str],
    changed_files: set[str],
    top_k: int,
) -> list[Candidate]:
    kw_lower = {k.lower() for k in keywords}
    # All extracted signals (paths, identifiers, quoted terms, plain words)
    # are merged into keywords by the classifier.  File hints are kept
    # separate because file-path matching is structurally different from
    # content matching.
    all_signals: set[str] = set(kw_lower)
    all_signals.update(h.lower() for h in file_hints)

    merged: dict[str, Candidate] = {}

    for cand in candidates:
        existing = merged.get(cand.chunk_id)
        if existing is None:
            merged[cand.chunk_id] = cand
        else:
            # Merge duplicate chunk hits, keeping the strongest source.
            if _SOURCE_WEIGHTS.get(cand.source, 0) > _SOURCE_WEIGHTS.get(existing.source, 0):
                existing.source = cand.source
            existing.base_score = max(existing.base_score, cand.base_score)
            existing.reasons.extend(r for r in cand.reasons if r not in existing.reasons)

    for cand in merged.values():
        cand.score = _score(cand, intent, kw_lower, file_hints, changed_files, all_signals)

    ranked = sorted(merged.values(), key=lambda c: c.score, reverse=True)
    return ranked[:top_k]


def _score(
    cand: Candidate,
    intent: Intent,
    kw_lower: set[str],
    file_hints: list[str],
    changed_files: set[str],
    all_signals: set[str],
) -> float:
    score = _SOURCE_WEIGHTS.get(cand.source, 1.0) + cand.base_score

    sym_lower = (cand.symbol_name or "").lower()
    content_lower = (cand.content or "").lower()

    # 1. Exact symbol name match (existing behaviour — strongest signal).
    if cand.symbol_name and sym_lower in kw_lower:
        score += 6.0
        cand.reasons.append("exact symbol match")

    # 2. Partial symbol name match — keyword is substring of symbol name or
    #    vice versa.  Generic: "verifications" matches "VerificationController",
    #    "kafka" matches "KafkaConsumerConfig".
    if sym_lower:
        for sig in all_signals:
            if is_partial_symbol_signal(sig) and (sig in sym_lower or sym_lower in sig):
                if sym_lower != sig:  # don't double-count exact match
                    score += 3.0
                    cand.reasons.append(f"partial symbol match '{sig}'")
                    break

    # 3. Signal found in content — any extracted signal (keyword, route_hint,
    #    file_hint, identifier) appearing in the chunk content.  Generic: a
    #    route path, a class name, any term the user mentioned.
    for sig in all_signals:
        if len(sig) >= 3 and sig in content_lower:
            score += 3.0
            cand.reasons.append(f"content matches '{sig}'")
            break

    name_lower = (cand.file_path or "").lower()
    if any(h.lower() in name_lower for h in file_hints):
        score += 4.0
        cand.reasons.append("file path match")

    if cand.file_path in changed_files:
        score += 3.0
        cand.reasons.append("recently changed")

    kind = (cand.symbol_type or "").lower()
    if intent == Intent.TEST_CREATION and kind == "test":
        score += 2.5
        cand.reasons.append("test relevant to intent")
    if intent == Intent.REVIEW and cand.file_path in changed_files:
        score += 2.0
    if kind == "route":
        score += 1.5
        cand.reasons.append("route handler")
    if kind in ("config", "bean"):
        score += 1.0
        cand.reasons.append("configuration")

    return score
