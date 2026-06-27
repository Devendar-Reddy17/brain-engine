"""Local embedding provider stub.

Placeholder for a future on-device model (e.g. sentence-transformers / a small
code embedding model). Until a real model is wired in, it lazily falls back to
the deterministic mock provider so the system keeps working offline.
"""

from __future__ import annotations

from brain.core.embeddings.embedding_provider import DEFAULT_DIM
from brain.core.embeddings.mock_embedding_provider import MockEmbeddingProvider
from brain.utils.logger import get_logger

log = get_logger(__name__)


class LocalEmbeddingProvider:
    def __init__(self, model: str = "local-code-embedding-small", dim: int = DEFAULT_DIM) -> None:
        self.model = model
        self.dim = dim
        self._impl: MockEmbeddingProvider | None = None
        # TODO: load a real local model here when available.
        log.info("Local embedding model not bundled yet; using deterministic fallback")

    def _provider(self) -> MockEmbeddingProvider:
        if self._impl is None:
            self._impl = MockEmbeddingProvider(model=self.model, dim=self.dim)
        return self._impl

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._provider().embed(texts)
