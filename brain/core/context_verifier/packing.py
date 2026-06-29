"""Chunk conversion, dedupe, and packing helpers."""

from __future__ import annotations

import hashlib

from brain.core.context_verifier.types import RetrievedChunk
from brain.core.retrieval.context_retriever import RetrievalResult
from brain.types.brain_types import ContextChunk, RelevantFile, TargetSymbol


def retrieved_chunks_from_result(result: RetrievalResult) -> list[RetrievedChunk]:
    return [retrieved_chunk_from_context_chunk(chunk) for chunk in result.chunks]


def retrieved_chunk_from_context_chunk(chunk: ContextChunk) -> RetrievedChunk:
    return RetrievedChunk(
        id=chunk_id(chunk.file, chunk.start_line, chunk.end_line, chunk.content),
        file_path=chunk.file,
        symbol_name=chunk.symbol,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        content=chunk.content,
        source=chunk.reason,
    )


def context_chunk_from_retrieved(chunk: RetrievedChunk) -> ContextChunk:
    return ContextChunk(
        file=chunk.file_path,
        symbol=chunk.symbol_name,
        start_line=chunk.start_line or 0,
        end_line=chunk.end_line or 0,
        reason=chunk.source or "context verifier",
        content=chunk.content,
    )


def chunk_id(file_path: str, start_line: int | None, end_line: int | None, content: str) -> str:
    digest = hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"{file_path}:{start_line or 0}-{end_line or 0}:{digest}"


def merge_and_dedupe_chunks(existing: list[RetrievedChunk], incoming: list[RetrievedChunk]) -> list[RetrievedChunk]:
    out: list[RetrievedChunk] = []
    seen: set[tuple[str, int | None, int | None, str]] = set()
    for chunk in [*existing, *incoming]:
        digest = hashlib.sha1(chunk.content.encode("utf-8", errors="ignore")).hexdigest()
        key = (chunk.file_path, chunk.start_line, chunk.end_line, digest)
        if key in seen:
            continue
        seen.add(key)
        out.append(chunk)
    return out


def pack_chunks(chunks: list[RetrievedChunk], keep_chunk_ids: list[str]) -> list[RetrievedChunk]:
    if keep_chunk_ids:
        keep = set(keep_chunk_ids)
        selected = [chunk for chunk in chunks if chunk.id in keep]
        if selected:
            return merge_and_dedupe_chunks([], selected)
    return merge_and_dedupe_chunks([], chunks)


def apply_verified_chunks(result: RetrievalResult, packed: list[RetrievedChunk]) -> None:
    result.chunks = [context_chunk_from_retrieved(chunk) for chunk in packed]
    result.relevant_files = _relevant_files(result.chunks)
    result.target_symbols = _target_symbols(result.chunks)
    if result.token_savings:
        result.token_savings.context_tokens = sum(max(1, len(c.content) // 4) for c in result.chunks)


def _relevant_files(chunks: list[ContextChunk]) -> list[RelevantFile]:
    seen: set[str] = set()
    out: list[RelevantFile] = []
    for chunk in chunks:
        if chunk.file in seen:
            continue
        seen.add(chunk.file)
        out.append(RelevantFile(path=chunk.file, reason=chunk.reason))
    return out


def _target_symbols(chunks: list[ContextChunk]) -> list[TargetSymbol]:
    seen: set[tuple[str, str]] = set()
    out: list[TargetSymbol] = []
    for chunk in chunks:
        if not chunk.symbol:
            continue
        key = (chunk.file, chunk.symbol)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            TargetSymbol(
                name=chunk.symbol,
                kind="method",
                file=chunk.file,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
            )
        )
    return out

