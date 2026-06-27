"""Vector (semantic) search over chunk embeddings.

Embeds the query with the configured provider and ranks indexed chunks by
cosine similarity. Vectors are stored normalized, so cosine reduces to a dot
product. For large repos this is a linear scan; adequate for the MVP and easily
swappable for an ANN index later.
"""

from __future__ import annotations

import math

from brain.core.db.repositories.chunk_repository import ChunkRepository
from brain.core.db.repositories.embedding_repository import EmbeddingRepository
from brain.core.embeddings.embedding_provider import EmbeddingProvider
from brain.core.retrieval.reranker import Candidate


class VectorSearch:
    def __init__(
        self,
        embeddings: EmbeddingRepository,
        chunks: ChunkRepository,
        embedder: EmbeddingProvider,
    ) -> None:
        self.embeddings = embeddings
        self.chunks = chunks
        self.embedder = embedder

    def search(self, query: str, *, top_k: int) -> list[Candidate]:
        vectors = self.embeddings.all_vectors()
        if not vectors:
            return []

        query_vec = self.embedder.embed([query])[0]
        scored: list[tuple[float, str]] = []
        for chunk_id, vec in vectors:
            scored.append((_cosine(query_vec, vec), chunk_id))
        scored.sort(reverse=True)

        candidates: list[Candidate] = []
        for sim, chunk_id in scored[:top_k]:
            if sim <= 0:
                continue
            row = self.chunks.get_by_chunk_id(chunk_id)
            if row is None:
                continue
            path_row = self.chunks.db.query_one(
                "SELECT path FROM files WHERE id = ?", (row["file_id"],)
            )
            candidates.append(
                Candidate(
                    chunk_id=chunk_id,
                    file_path=path_row["path"] if path_row else "",
                    symbol_name=row["symbol_name"],
                    symbol_type=row["symbol_type"],
                    start_line=row["start_line"] or 0,
                    end_line=row["end_line"] or 0,
                    content=row["content"] or "",
                    source="vector",
                    base_score=float(sim),
                    reasons=[f"semantic match ({sim:.2f})"],
                )
            )
        return candidates


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
