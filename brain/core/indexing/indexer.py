"""Full-repository indexer.

Orchestrates: scan -> hash gate -> parse -> symbols -> dependency edges ->
semantic chunks -> (re)embed changed chunks -> persist. Designed to be reused
per-file by the incremental indexer.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from brain.config.default_config import BrainConfig
from brain.core.db.database import Database
from brain.core.db.repositories.chunk_repository import ChunkRepository
from brain.core.db.repositories.dependency_repository import DependencyRepository
from brain.core.db.repositories.embedding_repository import EmbeddingRepository
from brain.core.db.repositories.file_repository import FileRepository
from brain.core.db.repositories.repo_state_repository import RepoStateRepository
from brain.core.db.repositories.symbol_repository import SymbolRepository
from brain.core.embeddings.embedding_provider import EmbeddingProvider
from brain.core.indexing import symbol_extractor
from brain.core.indexing.chunker import Chunk
from brain.core.indexing.dependency_graph_builder import build_edges
from brain.core.indexing.hash_gate import HashGate
from brain.core.indexing.semantic_chunker import chunk_file
from brain.core.repo.file_hasher import hash_file
from brain.core.repo.file_scanner import ScannedFile, scan_repo
from brain.core.repo.git_service import GitService
from brain.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class IndexResult:
    repo_root: str
    files_scanned: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    chunks_created: int = 0
    symbols_extracted: int = 0
    duration_ms: int = 0
    forced: bool = False
    total_files: int = 0
    total_chunks: int = 0
    total_symbols: int = 0
    errors: list[str] = field(default_factory=list)


class Indexer:
    def __init__(
        self,
        repo_root: str,
        db: Database,
        embedder: EmbeddingProvider,
        config: BrainConfig,
    ) -> None:
        self.repo_root = repo_root
        self.db = db
        self.config = config
        self.embedder = embedder
        self.files = FileRepository(db)
        self.chunks = ChunkRepository(db)
        self.symbols = SymbolRepository(db)
        self.deps = DependencyRepository(db)
        self.embeddings = EmbeddingRepository(db)
        self.repo_state = RepoStateRepository(db)
        self.gate = HashGate(self.files, self.chunks)
        self.git = GitService(repo_root)

    def full_index(self) -> IndexResult:
        start = time.time()
        result = IndexResult(repo_root=self.repo_root)
        self.repo_state.ensure(self.repo_root, self.git.current_branch())

        # A stale index was built by older parser/tagger/chunker/schema/embedding
        # code, so its derived data is outdated even though file *contents* are
        # unchanged. The hash gate keys off content only and would wrongly skip
        # every file, leaving the stale data in place while `mark_full_index`
        # clears the stale flag. Force a rebuild so a full index truly repairs a
        # stale repo. Only an *existing* index can be stale — a fresh repo's
        # files are new and get indexed regardless. Staleness is re-evaluated
        # here (not cleared) so versions are only updated after the forced
        # rebuild succeeds below.
        state = self.repo_state.get()
        already_indexed = bool(state and state["last_full_index_at"])
        is_stale = self.repo_state.is_stale() or bool(self.repo_state.detect_stale_components())
        force = already_indexed and is_stale
        result.forced = force

        scanned = scan_repo(self.repo_root)
        scanned_paths = {sf.rel_path for sf in scanned}
        for row in self.files.list_active():
            if row["path"] not in scanned_paths:
                self.files.mark_deleted(row["path"])
        result.files_scanned = len(scanned)
        log.info("Indexing %d files under %s (force=%s)", len(scanned), self.repo_root, force)

        for sf in scanned:
            try:
                indexed, n_chunks, n_symbols = self._index_scanned(sf, force=force)
                if indexed:
                    result.files_indexed += 1
                    result.chunks_created += n_chunks
                    result.symbols_extracted += n_symbols
                else:
                    result.files_skipped += 1
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed to index %s: %s", sf.rel_path, exc)
                result.errors.append(f"{sf.rel_path}: {exc}")

        # Only now (after a successful pass) record the build versions and clear
        # staleness, and snapshot the authoritative DB totals.
        self.repo_state.mark_full_index()
        result.total_files = self.files.count()
        result.total_chunks = self.chunks.count()
        result.total_symbols = self.symbols.count()
        result.duration_ms = int((time.time() - start) * 1000)
        log.info(
            "Index complete: %d indexed, %d skipped, %d chunks, %d symbols in %dms",
            result.files_indexed, result.files_skipped, result.chunks_created,
            result.symbols_extracted, result.duration_ms,
        )
        return result

    def index_path(self, rel_path: str, *, force: bool = True) -> tuple[bool, int, int]:
        """Index a single file by repo-relative path. Used incrementally."""

        abs_path = Path(self.repo_root) / rel_path
        if not abs_path.exists():
            self.files.mark_deleted(rel_path)
            return (False, 0, 0)

        from brain.core.repo.ignore_rules import detect_language
        from datetime import datetime, timezone

        language = detect_language(rel_path)
        if language is None:
            return (False, 0, 0)
        stat = abs_path.stat()
        sf = ScannedFile(
            path=str(abs_path),
            rel_path=rel_path,
            language=language,
            size_bytes=stat.st_size,
            last_modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        )
        return self._index_scanned(sf, force=force)

    # -- internals --------------------------------------------------------
    def _index_scanned(self, sf: ScannedFile, *, force: bool) -> tuple[bool, int, int]:
        file_hash = hash_file(sf.path)
        if not force and not self.gate.file_changed(sf.rel_path, file_hash):
            return (False, 0, 0)

        source = Path(sf.path).read_text(encoding="utf-8", errors="replace")
        file_id = self.files.upsert(
            path=sf.rel_path,
            language=sf.language,
            size_bytes=sf.size_bytes,
            file_hash=file_hash,
            last_modified_at=sf.last_modified_at,
        )

        parse_result = symbol_extractor.extract(source, sf.rel_path, sf.language)
        symbol_rows = symbol_extractor.to_symbol_rows(parse_result)
        name_to_id = self.symbols.replace_for_file(file_id, symbol_rows)

        source_ids, edges = build_edges(parse_result, name_to_id)
        self.deps.replace_for_sources(source_ids, edges)

        chunks = chunk_file(
            rel_path=sf.rel_path,
            language=sf.language,
            source=source,
            parse_result=parse_result,
            max_chunk_tokens=self.config.embedding.max_chunk_tokens,
        )
        self._persist_chunks(file_id, chunks)

        return (True, len(chunks), len(symbol_rows))

    def _persist_chunks(self, file_id: int, chunks: list[Chunk]) -> None:
        only_changed = self.config.embedding.only_embed_changed_chunks
        to_embed: list[Chunk] = []

        for chunk in chunks:
            changed = self.gate.chunk_changed(chunk.chunk_id, chunk.content_hash)
            if changed or not only_changed:
                to_embed.append(chunk)
            else:
                existing = self.chunks.get_by_chunk_id(chunk.chunk_id)
                chunk.embedding_id = existing["embedding_id"] if existing else None

        if to_embed:
            vectors = self.embedder.embed([c.content for c in to_embed])
            for chunk, vector in zip(to_embed, vectors):
                chunk.embedding_id = self.embeddings.upsert(
                    chunk_id=chunk.chunk_id, vector=vector, model=self.embedder.model
                )

        for chunk in chunks:
            self.chunks.upsert(
                file_id=file_id,
                chunk_id=chunk.chunk_id,
                symbol_name=chunk.symbol_name,
                symbol_type=chunk.symbol_type,
                language=chunk.language,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                content_hash=chunk.content_hash,
                content=chunk.content,
                embedding_id=chunk.embedding_id,
            )

        self.chunks.delete_missing(file_id, [c.chunk_id for c in chunks])
