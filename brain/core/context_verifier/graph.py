"""Simple chunk graph builder for verifier context."""

from __future__ import annotations

import re

from brain.core.context_verifier.types import ChunkGraph, ChunkGraphEdge, ChunkGraphNode, RetrievedChunk


IMPORT_PATTERNS = [
    re.compile(r"^\s*import\s+(?:[^'\"]+\s+from\s+)?['\"]([^'\"]+)['\"]", re.MULTILINE),
    re.compile(r"^\s*import\s+([\w.*]+)\s*;", re.MULTILINE),
    re.compile(r"^\s*from\s+([\w.]+)\s+import\s+([\w*, ]+)", re.MULTILINE),
    re.compile(r"^\s*import\s+([\w.]+)", re.MULTILINE),
]

ROUTE_PATTERNS = [
    re.compile(r"@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\s*(\([^)]*\))?"),
    re.compile(r"\b(router|app)\.(get|post|put|delete|patch|use)\s*\("),
]


def build_chunk_graph(chunks: list[RetrievedChunk]) -> ChunkGraph:
    nodes = [
        ChunkGraphNode(id=chunk.id, file_path=chunk.file_path, symbol_name=chunk.symbol_name)
        for chunk in chunks
    ]
    edges: list[ChunkGraphEdge] = []
    unresolved: list[str] = []

    by_symbol = {
        chunk.symbol_name: chunk
        for chunk in chunks
        if chunk.symbol_name
    }
    by_file_leaf = {leaf(chunk.file_path): chunk for chunk in chunks}

    for chunk in chunks:
        for imported in _imports(chunk.content):
            target = _resolve_import(imported, by_file_leaf, by_symbol)
            if target and target.id != chunk.id:
                edges.append(ChunkGraphEdge(from_=chunk.id, to=target.id, type="import", evidence=imported))
            elif imported not in unresolved:
                unresolved.append(imported)

        for symbol, target in by_symbol.items():
            if target.id == chunk.id or not symbol:
                continue
            if re.search(rf"\b{re.escape(symbol)}\b", chunk.content):
                edge_type = "test" if _is_test_path(chunk.file_path) else "reference"
                edges.append(ChunkGraphEdge(from_=chunk.id, to=target.id, type=edge_type, evidence=symbol))

        if _has_route(chunk.content):
            for symbol, target in by_symbol.items():
                if target.id != chunk.id and symbol and re.search(rf"\b{re.escape(symbol)}\b", chunk.content):
                    edges.append(ChunkGraphEdge(from_=chunk.id, to=target.id, type="route", evidence=symbol))

    return ChunkGraph(nodes=nodes, edges=_dedupe_edges(edges), unresolved_references=unresolved[:50])


def _imports(content: str) -> list[str]:
    out: list[str] = []
    for pattern in IMPORT_PATTERNS:
        for match in pattern.finditer(content):
            value = ".".join(g for g in match.groups() if g).strip()
            if value and value not in out:
                out.append(value)
    return out


def _resolve_import(
    imported: str,
    by_file_leaf: dict[str, RetrievedChunk],
    by_symbol: dict[str, RetrievedChunk],
) -> RetrievedChunk | None:
    tail = imported.rsplit(".", 1)[-1].replace("*", "")
    candidates = [tail, f"{tail}.ts", f"{tail}.tsx", f"{tail}.js", f"{tail}.py", f"{tail}.java"]
    for candidate in candidates:
        if candidate in by_file_leaf:
            return by_file_leaf[candidate]
        if candidate in by_symbol:
            return by_symbol[candidate]
    return None


def _has_route(content: str) -> bool:
    return any(pattern.search(content) for pattern in ROUTE_PATTERNS)


def _is_test_path(path: str) -> bool:
    lowered = path.lower()
    return "test" in lowered or "spec" in lowered


def leaf(path: str) -> str:
    normalized = path.replace("\\", "/")
    return normalized.rsplit("/", 1)[-1]


def _dedupe_edges(edges: list[ChunkGraphEdge]) -> list[ChunkGraphEdge]:
    seen: set[tuple[str, str, str, str | None]] = set()
    out: list[ChunkGraphEdge] = []
    for edge in edges:
        key = (edge.from_, edge.to, edge.type, edge.evidence)
        if key in seen:
            continue
        seen.add(key)
        out.append(edge)
    return out

