"""OpenAI-compatible embedding provider.

Calls a ``/embeddings`` endpoint compatible with the OpenAI API. The API key is
read from the environment variable named in config (``embedding.api_key_env``).
Only used when explicitly configured; never used by ``index``/``context`` unless
the user selects it.
"""

from __future__ import annotations

import os

from brain.core.embeddings.embedding_provider import DEFAULT_DIM
from brain.utils.errors import ConfigError
from brain.utils.logger import get_logger

log = get_logger(__name__)


class OpenAiCompatibleEmbeddingProvider:
    def __init__(self, *, base_url: str, api_key_env: str, model: str, dim: int = DEFAULT_DIM) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dim = dim
        self._api_key = os.environ.get(api_key_env, "")
        if not self._api_key:
            log.warning("Embedding API key env '%s' is not set", api_key_env)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise ConfigError("httpx is required for the OpenAI-compatible embedder") from exc

        resp = httpx.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self.model, "input": texts},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        items = sorted(data["data"], key=lambda d: d.get("index", 0))
        vectors = [item["embedding"] for item in items]
        if vectors:
            self.dim = len(vectors[0])
        return vectors
