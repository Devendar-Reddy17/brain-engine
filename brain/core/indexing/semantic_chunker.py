"""Semantic, symbol-aware chunking.

Preferred chunk order (per spec):
  1. method/function chunks
  2. class chunks (when a type has no method members)
  3. file-level fallback for unsupported languages / no symbols
  4. token-limit splitting only as a last resort (for oversized blocks)
"""

from __future__ import annotations

from brain.core.indexing.chunker import (
    Chunk,
    approx_tokens,
    build_chunk,
    split_by_token_limit,
)
from brain.core.parsing.parser import ParsedSymbol, ParseResult

_METHOD_KINDS = {"method", "function", "constructor", "route", "test"}
_TYPE_KINDS = {"class", "interface", "enum"}


def _slice(lines: list[str], start_line: int, end_line: int) -> str:
    start = max(0, start_line - 1)
    end = min(len(lines), end_line)
    return "\n".join(lines[start:end])


def _resolve_end(sym: ParsedSymbol, next_start: int | None, file_end: int) -> int:
    """Resolve a usable end line.

    Tree-sitter provides accurate end lines (end_line > start_line). The regex
    fallback sets end == start, so we approximate using the next symbol's start
    (capped to a window) to produce meaningful multi-line chunks.
    """

    if sym.end_line > sym.start_line:
        return sym.end_line
    if next_start is not None:
        return min(next_start - 1, sym.start_line + 60)
    return min(file_end, sym.start_line + 60)


def chunk_file(
    *,
    rel_path: str,
    language: str,
    source: str,
    parse_result: ParseResult,
    max_chunk_tokens: int,
) -> list[Chunk]:
    lines = source.splitlines()
    file_end = len(lines)
    chunks: list[Chunk] = []

    methods = [s for s in parse_result.symbols if s.kind in _METHOD_KINDS]
    types = [s for s in parse_result.symbols if s.kind in _TYPE_KINDS]

    # 3. File-level fallback when there are no meaningful symbols.
    if not methods and not types:
        return _file_level_chunks(rel_path, language, lines, max_chunk_tokens)

    method_starts = sorted({m.start_line for m in methods})

    # 1. Method/function chunks.
    for sym in methods:
        next_start = _next_start(method_starts, sym.start_line)
        end = _resolve_end(sym, next_start, file_end)
        content = _slice(lines, sym.start_line, end)
        if not content.strip():
            continue
        chunks.extend(
            _emit(rel_path, language, sym.name, sym.kind, sym.start_line, end, content, lines, max_chunk_tokens)
        )

    # 2. Class chunks for types with no method members.
    types_with_methods = {m.parent_symbol for m in methods}
    for sym in types:
        if sym.name in types_with_methods:
            # Add a compact header chunk (declaration region) for context.
            header_end = min(file_end, sym.start_line + 5)
            content = _slice(lines, sym.start_line, header_end)
            if content.strip():
                chunks.append(
                    build_chunk(
                        rel_path=rel_path, language=language, symbol_name=sym.name,
                        symbol_type=sym.kind, start_line=sym.start_line,
                        end_line=header_end, content=content,
                    )
                )
            continue
        end = _resolve_end(sym, None, file_end)
        content = _slice(lines, sym.start_line, end)
        if content.strip():
            chunks.extend(
                _emit(rel_path, language, sym.name, sym.kind, sym.start_line, end, content, lines, max_chunk_tokens)
            )

    if not chunks:
        return _file_level_chunks(rel_path, language, lines, max_chunk_tokens)
    return chunks


def _emit(rel_path, language, name, kind, start, end, content, lines, max_tokens) -> list[Chunk]:
    """Emit one chunk, or token-split if the block exceeds the budget."""

    if approx_tokens(content) <= max_tokens:
        return [
            build_chunk(
                rel_path=rel_path, language=language, symbol_name=name,
                symbol_type=kind, start_line=start, end_line=end, content=content,
            )
        ]
    block_lines = lines[max(0, start - 1):min(len(lines), end)]
    return split_by_token_limit(
        rel_path=rel_path, language=language, symbol_name=name, symbol_type=kind,
        start_line=start, lines=block_lines, max_tokens=max_tokens,
    )


def _file_level_chunks(rel_path, language, lines, max_tokens) -> list[Chunk]:
    content = "\n".join(lines)
    if not content.strip():
        return []
    if approx_tokens(content) <= max_tokens:
        return [
            build_chunk(
                rel_path=rel_path, language=language, symbol_name=None,
                symbol_type="file", start_line=1, end_line=len(lines), content=content,
            )
        ]
    return split_by_token_limit(
        rel_path=rel_path, language=language, symbol_name=None, symbol_type="file",
        start_line=1, lines=lines, max_tokens=max_tokens,
    )


def _next_start(sorted_starts: list[int], current: int) -> int | None:
    for s in sorted_starts:
        if s > current:
            return s
    return None
