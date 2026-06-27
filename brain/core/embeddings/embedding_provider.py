"""EmbeddingProvider interface and factory.

Providers turn text into fixed-size vectors. The MVP default is the
deterministic mock provider, which requires no external dependency. An
OpenAI-compatible provider and a local-model stub are also available and
selected via config (``embedding.provider``).
"""

from __future__ import annotations

from typing import Protocol

from brain.config.default_config import BrainConfig
from brain.utils.logger import get_logger

log = get_logger(__name__)

DEFAULT_DIM = 256


class EmbeddingProvider(Protocol):
    model: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - protocol
        ...


def get_embedding_provider(config: BrainConfig) -> EmbeddingProvider:
    provider = (config.embedding.provider or "mock").lower()
    model = config.embedding.model

    if provider in ("openai", "openai-compatible") and config.embedding.base_url:
        from brain.core.embeddings.openai_compatible_embedding_provider import (
            OpenAiCompatibleEmbeddingProvider,
        )

        return OpenAiCompatibleEmbeddingProvider(
            base_url=config.embedding.base_url,
            api_key_env=config.embedding.api_key_env,
            model=model,
        )

    if provider == "local":
        from brain.core.embeddings.local_embedding_provider import LocalEmbeddingProvider

        return LocalEmbeddingProvider(model=model)

    if provider not in ("mock", "openai", "openai-compatible", "local"):
        log.warning("Unknown embedding provider '%s'; falling back to mock", provider)

    from brain.core.embeddings.mock_embedding_provider import MockEmbeddingProvider

    return MockEmbeddingProvider(model=model)
