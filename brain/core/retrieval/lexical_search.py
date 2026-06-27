"""Lexical search over symbol names and chunk content."""

from __future__ import annotations

from brain.core.db.repositories.chunk_repository import ChunkRepository
from brain.core.db.repositories.symbol_repository import SymbolRepository
from brain.core.retrieval.intent_classifier import is_noise_term
from brain.core.retrieval.reranker import Candidate


class LexicalSearch:
    def __init__(self, chunks: ChunkRepository, symbols: SymbolRepository) -> None:
        self.chunks = chunks
        self.symbols = symbols

    def search(self, keywords: list[str], *, top_k: int) -> list[Candidate]:
        candidates: list[Candidate] = []
        seen: set[str] = set()

        for kw in keywords[:12]:
            # Exact symbol-name matches map to chunks for that symbol.
            for row in self.symbols.find_by_name(kw, limit=top_k):
                for chunk in self.chunks.list_by_file(row["file_id"]):
                    if chunk["symbol_name"] == row["name"]:
                        self._add(candidates, seen, chunk, source="symbol",
                                  base=2.0, reason=f"symbol '{kw}'")

            # Partial (LIKE) symbol-name matches — lower priority than exact.
            for row in self.symbols.search_by_name(kw, limit=top_k):
                for chunk in self.chunks.list_by_file(row["file_id"]):
                    if chunk["symbol_name"] == row["name"]:
                        self._add(candidates, seen, chunk, source="symbol_partial",
                                  base=1.5, reason=f"partial symbol '{kw}'")

            # Content matches — skip noise terms that match too many chunks.
            if not is_noise_term(kw):
                for chunk in self.chunks.search_content(kw, limit=top_k):
                    self._add(candidates, seen, chunk, source="lexical",
                              base=1.0, reason=f"matches '{kw}'")

        return candidates

    def _add(self, out: list[Candidate], seen: set[str], row, *, source: str, base: float, reason: str) -> None:
        chunk_id = row["chunk_id"]
        if chunk_id in seen:
            return
        seen.add(chunk_id)
        file_path = row["file_path"] if "file_path" in row.keys() else None
        if file_path is None:
            # search_content rows include file_path; list_by_file rows don't.
            file_path = self._resolve_path(row["file_id"])
        out.append(
            Candidate(
                chunk_id=chunk_id,
                file_path=file_path or "",
                symbol_name=row["symbol_name"],
                symbol_type=row["symbol_type"],
                start_line=row["start_line"] or 0,
                end_line=row["end_line"] or 0,
                content=row["content"] or "",
                source=source,
                base_score=base,
                reasons=[reason],
            )
        )

    def _resolve_path(self, file_id: int) -> str | None:
        row = self.chunks.db.query_one("SELECT path FROM files WHERE id = ?", (file_id,))
        return row["path"] if row else None
