"""Deterministic, dependency-free embedding provider for the MVP.

Produces a stable hashed bag-of-tokens vector so the system works offline and
gives repeatable vector-search results. Not semantically rich, but adequate for
lexical-adjacent retrieval and for exercising the full pipeline.
"""

from __future__ import annotations

import math
import re

from brain.core.embeddings.embedding_provider import DEFAULT_DIM

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class MockEmbeddingProvider:
    def __init__(self, model: str = "mock-embedding", dim: int = DEFAULT_DIM) -> None:
        self.model = model
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = _TOKEN_RE.findall(text.lower())
        if not tokens:
            return vec
        for token in tokens:
            # Stable hash -> bucket; weight by inverse length to vary signal.
            h = self._stable_hash(token)
            idx = h % self.dim
            vec[idx] += 1.0
        # L2 normalize for cosine similarity.
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    @staticmethod
    def _stable_hash(token: str) -> int:
        h = 2166136261
        for ch in token:
            h ^= ord(ch)
            h = (h * 16777619) & 0xFFFFFFFF
        return h
