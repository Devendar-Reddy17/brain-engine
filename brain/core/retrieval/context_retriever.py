"""Context retriever: the heart of the retrieval pipeline.

Flow: intent classification -> lexical + vector search -> graph expansion ->
rerank -> token-budget packing -> dependency context -> git diff -> confidence
-> token savings. Produces a :class:`RetrievalResult` consumed by the packer
and the API.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from brain.config.default_config import BrainConfig
from brain.core.db.database import Database
from brain.core.db.repositories.chunk_repository import ChunkRepository
from brain.core.db.repositories.dependency_repository import DependencyRepository
from brain.core.db.repositories.embedding_repository import EmbeddingRepository
from brain.core.db.repositories.file_repository import FileRepository
from brain.core.db.repositories.symbol_repository import SymbolRepository
from brain.core.embeddings.embedding_provider import EmbeddingProvider
from brain.core.indexing.chunker import approx_tokens
from brain.core.repo.git_service import GitService
from brain.core.retrieval import confidence_scorer, intent_classifier
from brain.core.retrieval.lexical_search import LexicalSearch
from brain.core.retrieval.prompt_resolvers import resolve_prompt_candidates
from brain.core.retrieval.reranker import Candidate, rerank
from brain.core.retrieval.token_savings_estimator import TokenSavingsEstimator
from brain.core.retrieval.vector_search import VectorSearch
from brain.types.brain_types import (
    ContextChunk,
    DependencyContext,
    Intent,
    RelevantFile,
    TargetSymbol,
    TokenSavings,
)
from brain.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class RetrievalResult:
    prompt: str
    intent: Intent
    confidence: float = 0.0
    confidence_reason: str = ""
    token_savings: TokenSavings | None = None
    relevant_files: list[RelevantFile] = field(default_factory=list)
    target_symbols: list[TargetSymbol] = field(default_factory=list)
    chunks: list[ContextChunk] = field(default_factory=list)
    dependency_context: DependencyContext = field(default_factory=DependencyContext)
    git_diff_summary: str | None = None
    git_diff_full: str | None = None
    missing_context_warnings: list[str] = field(default_factory=list)
    markdown: str = ""


class ContextRetriever:
    def __init__(
        self,
        repo_root: str,
        db: Database,
        embedder: EmbeddingProvider,
        config: BrainConfig,
    ) -> None:
        self.repo_root = repo_root
        self.config = config
        self.files = FileRepository(db)
        self.chunks = ChunkRepository(db)
        self.symbols = SymbolRepository(db)
        self.deps = DependencyRepository(db)
        self.embeddings = EmbeddingRepository(db)
        self.lexical = LexicalSearch(self.chunks, self.symbols)
        self.vector = VectorSearch(self.embeddings, self.chunks, embedder)
        self.token_savings = TokenSavingsEstimator(self.files, self.chunks)
        self.git = GitService(repo_root)

    def retrieve(self, prompt: str, *, intent: Intent | None = None, include_full_diff: bool = False) -> RetrievalResult:
        rc = self.config.retrieval
        classified = intent_classifier.classify(prompt)
        final_intent = intent or classified.intent
        result = RetrievalResult(prompt=prompt, intent=final_intent)

        changed_files = set(self.git.changed_files())

        # 1. lexical + vector candidates
        candidates: list[Candidate] = []
        resolver_candidates = resolve_prompt_candidates(prompt, self.files, self.chunks, self.deps)
        candidates.extend(resolver_candidates)
        if resolver_candidates:
            # Strong resolvers (exact route/file hints) already identified the
            # right area. Skip broad lexical/vector search so generic terms do
            # not refill the pack with noise.
            pass
        else:
            candidates.extend(self.lexical.search(classified.keywords, top_k=rc.lexical_top_k))
            candidates.extend(self.vector.search(prompt, top_k=rc.vector_top_k))

        # 2. graph expansion + dependency context
        dep_ctx = DependencyContext()
        graph_candidates = self._expand_graph(candidates, classified.keywords, dep_ctx, rc, intent=final_intent)
        candidates.extend(graph_candidates)

        had_exact_symbol = any(
            c.symbol_name and c.symbol_name.lower() in {k.lower() for k in classified.keywords}
            for c in candidates
        )
        had_file_match = any(
            any(h.lower() in (c.file_path or "").lower() for h in classified.file_hints)
            for c in candidates
        )

        # 3. rerank
        ranked = rerank(
            candidates,
            intent=final_intent,
            keywords=classified.keywords,
            file_hints=classified.file_hints,
            changed_files=changed_files,
            top_k=max(rc.rerank_top_k, rc.symbol_top_k),
        )

        # 4. token-budget packing
        packed = self._pack_to_budget(ranked, rc.max_context_tokens)
        result.chunks = [self._to_context_chunk(c) for c in packed]
        result.relevant_files = self._relevant_files(packed)
        result.target_symbols = self._target_symbols(packed)
        result.dependency_context = dep_ctx

        # 5. git diff
        if rc.include_git_diff:
            summary = self.git.diff_summary()
            result.git_diff_summary = summary or None
            if include_full_diff:
                result.git_diff_full = self.git.diff() or None

        # 6. confidence
        conf, reason = confidence_scorer.score(
            ranked, keywords=classified.keywords,
            had_exact_symbol=had_exact_symbol, had_file_match=had_file_match,
        )
        result.confidence = conf
        result.confidence_reason = reason

        # 7. token savings (local, offline)
        result.token_savings = self.token_savings.estimate(
            [c.content for c in result.chunks], repo_root=self.repo_root
        )

        # 8. missing-context warnings
        result.missing_context_warnings = self._warnings(result, classified)
        return result

    # -- helpers ----------------------------------------------------------
    def _expand_graph(self, candidates: list[Candidate], keywords: list[str], dep_ctx: DependencyContext, rc, *, intent: Intent | None = None) -> list[Candidate]:
        graph: list[Candidate] = []
        seen_chunks = {c.chunk_id for c in candidates}

        # Start graph expansion only from strong matches (symbol hits), not
        # from weak content matches that are likely irrelevant.
        symbol_names = {c.symbol_name for c in candidates if c.symbol_name and c.base_score >= 1.5}
        symbol_names.update(keywords)

        for name in list(symbol_names)[: rc.symbol_top_k]:
            sym_rows = self.symbols.find_by_name(name, limit=5)
            for sym in sym_rows:
                sid = sym["id"]
                if rc.include_callees:
                    for edge in self.deps.callees_of(sid):
                        if edge["edge_type"] == "calls" and edge["target_symbol_name"]:
                            dep_ctx.callees.append(edge["target_symbol_name"])
                for edge in self.deps.callees_of(sid):
                    et = edge["edge_type"]
                    tgt = edge["target_symbol_name"]
                    if not tgt:
                        continue
                    if et == "implements":
                        dep_ctx.interfaces.append(tgt)
                    elif et == "extends":
                        dep_ctx.implementations.append(tgt)
                    elif et == "configures":
                        dep_ctx.configs.append(tgt)
                    elif et == "routes_to":
                        dep_ctx.routes.append(tgt)
            if rc.include_callers:
                for edge in self.deps.callers_of(name):
                    if edge["source_name"]:
                        dep_ctx.callers.append(edge["source_name"])
            for edge in self.deps.by_edge_type(name, "tested_by"):
                if edge["target_symbol_name"]:
                    dep_ctx.tests.append(edge["target_symbol_name"])

            # Add graph-neighbour chunks for the matched symbol's file.
            for sym in sym_rows:
                for chunk in self.chunks.list_by_file(sym["file_id"]):
                    if chunk["chunk_id"] in seen_chunks:
                        continue
                    seen_chunks.add(chunk["chunk_id"])
                    path_row = self.chunks.db.query_one(
                        "SELECT path FROM files WHERE id = ?", (sym["file_id"],)
                    )
                    graph.append(
                        Candidate(
                            chunk_id=chunk["chunk_id"],
                            file_path=path_row["path"] if path_row else "",
                            symbol_name=chunk["symbol_name"],
                            symbol_type=chunk["symbol_type"],
                            start_line=chunk["start_line"] or 0,
                            end_line=chunk["end_line"] or 0,
                            content=chunk["content"] or "",
                            source="graph",
                            base_score=0.5,
                            reasons=[f"graph neighbour of '{name}'"],
                        )
                    )

        # Deeper call-graph traversal for explanation queries (e.g. "explain
        # payment flow", "how does verification work").  Traverse ``calls``
        # edges 2 levels deep from matched symbols and include their chunks.
        # Generic — works for any topic the user asks about.
        if intent == Intent.ARCHITECTURE_EXPLANATION:
            self._deep_call_traversal(symbol_names, seen_chunks, graph, rc, depth=2)

        _dedup_in_place(dep_ctx)
        return graph

    def _deep_call_traversal(self, symbol_names: set[str], seen_chunks: set[str], graph: list[Candidate], rc, depth: int) -> None:
        """Traverse ``calls`` edges *depth* levels deep, adding chunks for encountered symbols."""

        visited_syms: set[int] = set()
        current_names = set(symbol_names)

        for _level in range(depth):
            next_names: set[str] = set()
            for name in list(current_names)[: rc.symbol_top_k]:
                sym_rows = self.symbols.find_by_name(name, limit=5)
                for sym in sym_rows:
                    sid = sym["id"]
                    if sid in visited_syms:
                        continue
                    visited_syms.add(sid)

                    # Follow calls edges to find callees.
                    for edge in self.deps.callees_of(sid):
                        if edge["edge_type"] == "calls" and edge["target_symbol_name"]:
                            callee_name = edge["target_symbol_name"]
                            next_names.add(callee_name)

                            # Add chunks for the callee symbol's file.
                            callee_rows = self.symbols.find_by_name(callee_name, limit=5)
                            for callee_sym in callee_rows:
                                for chunk in self.chunks.list_by_file(callee_sym["file_id"]):
                                    if chunk["chunk_id"] in seen_chunks:
                                        continue
                                    seen_chunks.add(chunk["chunk_id"])
                                    path_row = self.chunks.db.query_one(
                                        "SELECT path FROM files WHERE id = ?", (callee_sym["file_id"],)
                                    )
                                    graph.append(
                                        Candidate(
                                            chunk_id=chunk["chunk_id"],
                                            file_path=path_row["path"] if path_row else "",
                                            symbol_name=chunk["symbol_name"],
                                            symbol_type=chunk["symbol_type"],
                                            start_line=chunk["start_line"] or 0,
                                            end_line=chunk["end_line"] or 0,
                                            content=chunk["content"] or "",
                                            source="graph",
                                            base_score=0.4,
                                            reasons=[f"call-graph callee of '{name}'"],
                                        )
                                    )
            current_names = next_names

    def _pack_to_budget(self, ranked: list[Candidate], max_tokens: int) -> list[Candidate]:
        packed: list[Candidate] = []
        used = 0
        for cand in ranked:
            cost = approx_tokens(cand.content)
            if packed and used + cost > max_tokens:
                continue
            packed.append(cand)
            used += cost
            if used >= max_tokens:
                break
        return packed

    def _to_context_chunk(self, c: Candidate) -> ContextChunk:
        return ContextChunk(
            file=c.file_path,
            symbol=c.symbol_name,
            start_line=c.start_line,
            end_line=c.end_line,
            reason=c.reason,
            content=c.content,
        )

    def _relevant_files(self, packed: list[Candidate]) -> list[RelevantFile]:
        out: list[RelevantFile] = []
        seen: set[str] = set()
        for c in packed:
            if c.file_path in seen:
                continue
            seen.add(c.file_path)
            out.append(RelevantFile(path=c.file_path, reason=c.reason))
        return out

    def _target_symbols(self, packed: list[Candidate]) -> list[TargetSymbol]:
        out: list[TargetSymbol] = []
        seen: set[str] = set()
        for c in packed:
            if not c.symbol_name:
                continue
            key = f"{c.file_path}:{c.symbol_name}"
            if key in seen:
                continue
            seen.add(key)
            out.append(
                TargetSymbol(
                    name=c.symbol_name,
                    kind=c.symbol_type or "method",
                    file=c.file_path,
                    start_line=c.start_line,
                    end_line=c.end_line,
                )
            )
        return out

    def _warnings(self, result: RetrievalResult, classified: intent_classifier.IntentResult) -> list[str]:
        warnings: list[str] = []
        if not result.chunks:
            warnings.append("No code chunks matched; the repository may not be indexed yet.")
        if result.confidence < 0.4:
            warnings.append("Low confidence: relevant context may be missing. Consider refining the prompt.")
        for hint in classified.file_hints:
            if not any(hint.lower() in rf.path.lower() for rf in result.relevant_files):
                warnings.append(f"Referenced file '{hint}' was not found in the index.")
        return warnings


def _dedup_in_place(dep: DependencyContext) -> None:
    for attr in ("callers", "callees", "interfaces", "implementations", "configs", "routes", "tests"):
        values = getattr(dep, attr)
        setattr(dep, attr, list(dict.fromkeys(values)))
