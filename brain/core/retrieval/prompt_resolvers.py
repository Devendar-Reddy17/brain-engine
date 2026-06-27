"""Prompt-aware retrieval resolvers.

Resolvers add high-confidence context seeds before generic lexical/vector
search. They are deliberately language-agnostic where possible: parsers/taggers
normalize framework facts into graph edges and symbols, then resolvers consume
those normalized facts.

New frameworks should plug in here (or in sibling modules) instead of adding
case-by-case logic to ``ContextRetriever``.
"""

from __future__ import annotations

import re
from typing import Protocol

from brain.core.db.repositories.chunk_repository import ChunkRepository
from brain.core.db.repositories.dependency_repository import DependencyRepository
from brain.core.db.repositories.file_repository import FileRepository
from brain.core.retrieval.reranker import Candidate

_HTTP_ROUTE_RE = re.compile(
    r"\b(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(/[A-Za-z0-9_{}/:.-]+)",
    re.IGNORECASE,
)
_FILE_HINT_RE = re.compile(r"\b[\w./\\-]+\.[A-Za-z]{1,6}\b")

_LAYER_DIRS = {
    "component",
    "components",
    "controller",
    "controllers",
    "dto",
    "dtos",
    "entity",
    "entities",
    "handler",
    "handlers",
    "hook",
    "hooks",
    "model",
    "models",
    "page",
    "pages",
    "repository",
    "repositories",
    "route",
    "routes",
    "service",
    "services",
    "store",
    "stores",
    "view",
    "views",
}

_SUPPORT_DIRS = _LAYER_DIRS - {"controller", "controllers", "handler", "handlers", "route", "routes"}
_SUPPORT_NAME_PARTS = {
    "component",
    "dto",
    "entity",
    "hook",
    "model",
    "page",
    "repository",
    "service",
    "store",
    "view",
}


class PromptResolver(Protocol):
    def resolve(self, prompt: str, ctx: "ResolverContext") -> list[Candidate]:
        ...


class ResolverContext:
    def __init__(self, files: FileRepository, chunks: ChunkRepository, deps: DependencyRepository) -> None:
        self.files = files
        self.chunks = chunks
        self.deps = deps


class ExactRouteResolver:
    """Resolve prompts that name an exact HTTP route like ``GET /api/users/{id}``."""

    def resolve(self, prompt: str, ctx: ResolverContext) -> list[Candidate]:
        route = _extract_http_route(prompt)
        if route is None:
            return []

        candidates: list[Candidate] = []
        seen: set[str] = set()
        target = _normalize_route(route)

        for edge in ctx.deps.list_by_edge_type("routes_to", limit=5000):
            if _normalize_route(edge["target_symbol_name"] or "") != target:
                continue

            source_file = edge["source_file"] or ""
            source_name = edge["source_name"] or ""
            file_row = ctx.files.get_by_path(source_file)
            if file_row is None:
                continue

            for chunk in ctx.chunks.list_by_file(file_row["id"]):
                if chunk["chunk_id"] in seen:
                    continue
                if source_name and chunk["symbol_name"] != source_name:
                    continue
                seen.add(chunk["chunk_id"])
                candidates.append(
                    _candidate_from_chunk(
                        chunk,
                        source_file,
                        source="route_exact",
                        base_score=6.0,
                        reason=f"exact route '{route}'",
                    )
                )

            candidates.extend(_feature_context_candidates(ctx, source_file, seen))

        return candidates


class FileHintResolver:
    """Resolve prompts that name concrete files, independent of language."""

    def resolve(self, prompt: str, ctx: ResolverContext) -> list[Candidate]:
        hints = [_normalize_path_hint(h) for h in _FILE_HINT_RE.findall(prompt)]
        if not hints:
            return []

        candidates: list[Candidate] = []
        seen: set[str] = set()
        for row in ctx.files.list_active():
            path = row["path"]
            path_lower = path.lower()
            if not any(h.lower() in path_lower for h in hints):
                continue
            for chunk in ctx.chunks.list_by_file(row["id"]):
                if chunk["chunk_id"] in seen:
                    continue
                seen.add(chunk["chunk_id"])
                candidates.append(
                    _candidate_from_chunk(
                        chunk,
                        path,
                        source="file_hint",
                        base_score=4.0,
                        reason="file named in prompt",
                    )
                )
        return candidates


_RESOLVERS: tuple[PromptResolver, ...] = (
    ExactRouteResolver(),
    FileHintResolver(),
)


def resolve_prompt_candidates(prompt: str, files: FileRepository, chunks: ChunkRepository, deps: DependencyRepository) -> list[Candidate]:
    ctx = ResolverContext(files, chunks, deps)
    candidates: list[Candidate] = []
    for resolver in _RESOLVERS:
        candidates.extend(resolver.resolve(prompt, ctx))
    return candidates


def _candidate_from_chunk(chunk, file_path: str, *, source: str, base_score: float, reason: str) -> Candidate:
    return Candidate(
        chunk_id=chunk["chunk_id"],
        file_path=file_path,
        symbol_name=chunk["symbol_name"],
        symbol_type=chunk["symbol_type"],
        start_line=chunk["start_line"] or 0,
        end_line=chunk["end_line"] or 0,
        content=chunk["content"] or "",
        source=source,
        base_score=base_score,
        reasons=[reason],
    )


def _feature_context_candidates(ctx: ResolverContext, source_file: str, seen: set[str]) -> list[Candidate]:
    feature_root = _feature_root(source_file)
    if not feature_root:
        return []

    candidates: list[Candidate] = []
    for row in ctx.files.list_active():
        path = row["path"]
        if not path.startswith(feature_root + "/"):
            continue
        if not _is_feature_support_file(path):
            continue
        for chunk in ctx.chunks.list_by_file(row["id"]):
            if chunk["chunk_id"] in seen:
                continue
            seen.add(chunk["chunk_id"])
            candidates.append(
                _candidate_from_chunk(
                    chunk,
                    path,
                    source="feature_context",
                    base_score=2.0,
                    reason=f"same feature area as '{source_file}'",
                )
            )
    return candidates


def _extract_http_route(prompt: str) -> str | None:
    match = _HTTP_ROUTE_RE.search(prompt)
    if not match:
        return None
    return f"{match.group(1).upper()} {match.group(2)}"


def _normalize_route(route: str) -> str:
    parts = route.strip().split(maxsplit=1)
    if len(parts) != 2:
        return route.strip().lower().rstrip("/")
    method, path = parts
    return f"{method.upper()} {_normalize_route_path(path)}".lower()


def _normalize_route_path(path: str) -> str:
    path = path.strip().rstrip("/") or "/"
    # Treat Express/FastAPI ":id" and Spring "{id}" route variables as equivalent.
    return re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", path)


def _normalize_path_hint(hint: str) -> str:
    return hint.replace("\\", "/")


def _feature_root(source_file: str) -> str | None:
    parts = source_file.replace("\\", "/").split("/")
    for i, part in enumerate(parts):
        if part.lower() in _LAYER_DIRS:
            return "/".join(parts[:i])
    if len(parts) > 1:
        return "/".join(parts[:-1])
    return None


def _is_feature_support_file(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    parts = normalized.split("/")
    if any(part in _SUPPORT_DIRS for part in parts):
        return True
    stem = parts[-1].rsplit(".", 1)[0]
    return any(_filename_has_role(stem, role) for role in _SUPPORT_NAME_PARTS)


def _filename_has_role(stem: str, role: str) -> bool:
    return (
        stem == role
        or stem.endswith(role)
        or re.search(rf"(^|[._-]){re.escape(role)}s?($|[._-])", stem) is not None
    )
