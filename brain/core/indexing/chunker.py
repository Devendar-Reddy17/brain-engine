"""Low-level chunk primitives and token-limit splitting.

This module provides the :class:`Chunk` dataclass plus a deterministic
character-based token approximation and a last-resort token-limit splitter used
by the semantic chunker when a single symbol exceeds the configured budget.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from brain.core.repo.file_hasher import hash_text

# Approximate tokens as characters / 4 (matches the token-savings estimator).
CHARS_PER_TOKEN = 4


@dataclass
class Chunk:
    chunk_id: str
    file_path: str
    language: str
    symbol_name: str | None
    symbol_type: str | None
    start_line: int
    end_line: int
    content_hash: str
    content: str
    embedding_id: int | None = None


def approx_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def make_chunk_id(rel_path: str, symbol_name: str | None, start_line: int, index: int = 0) -> str:
    """Deterministic chunk id from path + symbol + position."""

    key = f"{rel_path}::{symbol_name or 'file'}::{start_line}::{index}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def build_chunk(
    *,
    rel_path: str,
    language: str,
    symbol_name: str | None,
    symbol_type: str | None,
    start_line: int,
    end_line: int,
    content: str,
    index: int = 0,
) -> Chunk:
    return Chunk(
        chunk_id=make_chunk_id(rel_path, symbol_name, start_line, index),
        file_path=rel_path,
        language=language,
        symbol_name=symbol_name,
        symbol_type=symbol_type,
        start_line=start_line,
        end_line=end_line,
        content_hash=hash_text(content),
        content=content,
    )


def split_by_token_limit(
    *,
    rel_path: str,
    language: str,
    symbol_name: str | None,
    symbol_type: str | None,
    start_line: int,
    lines: list[str],
    max_tokens: int,
) -> list[Chunk]:
    """Split a block of source ``lines`` into chunks under ``max_tokens``.

    Last-resort splitter: preserves line ordering and approximate line numbers.
    """

    chunks: list[Chunk] = []
    buffer: list[str] = []
    buffer_start = start_line
    index = 0

    def flush(end_line: int) -> None:
        nonlocal buffer, buffer_start, index
        if not buffer:
            return
        content = "\n".join(buffer)
        chunks.append(
            build_chunk(
                rel_path=rel_path,
                language=language,
                symbol_name=symbol_name,
                symbol_type=symbol_type,
                start_line=buffer_start,
                end_line=end_line,
                content=content,
                index=index,
            )
        )
        index += 1
        buffer = []

    current_line = start_line
    for line in lines:
        tentative = "\n".join([*buffer, line])
        if buffer and approx_tokens(tentative) > max_tokens:
            flush(current_line - 1)
            buffer_start = current_line
        buffer.append(line)
        current_line += 1

    flush(current_line - 1)
    return chunks
