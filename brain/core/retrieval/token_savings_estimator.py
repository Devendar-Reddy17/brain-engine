"""Token savings estimation (local, offline, deterministic).

Estimates how many tokens a full-repo dump would cost versus the packed
context, so the product can demonstrate measurable reduction. No external/AI
APIs are ever called.

The :class:`TokenEstimator` interface is future-proof: the default
:class:`ApproxTokenEstimator` uses ``chars / 4``, and can later be swapped for
tiktoken / Claude / OpenAI / model-specific tokenizers without touching
retrieval logic.
"""

from __future__ import annotations

from typing import Protocol

from brain.core.db.repositories.chunk_repository import ChunkRepository
from brain.core.db.repositories.file_repository import FileRepository
from brain.types.brain_types import TokenSavings
from brain.utils.logger import get_logger

log = get_logger(__name__)

CHARS_PER_TOKEN = 4
WORDS_TO_TOKENS = 1.3


class TokenEstimator(Protocol):
    def count(self, text: str) -> int:  # pragma: no cover - protocol
        ...


class ApproxTokenEstimator:
    """Deterministic approximation: ``len(text) / 4`` (chars-per-token)."""

    def __init__(self, chars_per_token: int = CHARS_PER_TOKEN) -> None:
        self.chars_per_token = chars_per_token

    def count(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // self.chars_per_token)


class WordTokenEstimator:
    """Alternative approximation: ``words * 1.3``."""

    def count(self, text: str) -> int:
        words = len(text.split())
        return int(words * WORDS_TO_TOKENS)


class TokenSavingsEstimator:
    """Compute repo vs packed-context token estimates and reduction."""

    def __init__(
        self,
        files: FileRepository,
        chunks: ChunkRepository,
        estimator: TokenEstimator | None = None,
    ) -> None:
        self.files = files
        self.chunks = chunks
        self.estimator = estimator or ApproxTokenEstimator()

    def estimate_repo_tokens(self, repo_root: str | None = None) -> int:
        """Estimate total tokens for the whole indexed repository.

        Uses indexed file sizes from SQLite (bytes / chars_per_token) to avoid a
        full filesystem rescan. ``repo_root`` is accepted for interface
        compatibility and future tokenizer-based scanning.
        """

        total_bytes = self.files.total_size_bytes()
        chars_per_token = getattr(self.estimator, "chars_per_token", CHARS_PER_TOKEN)
        return max(0, int(total_bytes / chars_per_token))

    def estimate_context_tokens(self, context_chunks: list[str]) -> int:
        return sum(self.estimator.count(chunk) for chunk in context_chunks)

    def calculate_reduction(self, repo_tokens: int, context_tokens: int) -> float:
        if repo_tokens <= 0:
            return 0.0
        reduction = (1.0 - (context_tokens / repo_tokens)) * 100.0
        return round(max(0.0, min(100.0, reduction)), 1)

    def build_summary(
        self,
        repo_tokens: int,
        context_tokens: int,
        reduction_percentage: float,
    ) -> dict:
        return {
            "repoTokens": repo_tokens,
            "contextTokens": context_tokens,
            "reductionPercentage": reduction_percentage,
        }

    def estimate(self, context_chunks: list[str], repo_root: str | None = None) -> TokenSavings:
        """Convenience: compute the full :class:`TokenSavings` in one call."""

        repo_tokens = self.estimate_repo_tokens(repo_root)
        context_tokens = self.estimate_context_tokens(context_chunks)
        reduction = self.calculate_reduction(repo_tokens, context_tokens)
        log.info("Repository Tokens: %d", repo_tokens)
        log.info("Context Tokens: %d", context_tokens)
        log.info("Token Reduction: %.1f%%", reduction)
        return TokenSavings(
            repo_tokens=repo_tokens,
            context_tokens=context_tokens,
            reduction_percentage=reduction,
        )
