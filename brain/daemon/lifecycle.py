"""Brain engine lifecycle: owns all stateful components for one repo.

Holds the database, embedder, indexer, retriever, and the watch subsystem.
Exposes high-level operations used by the API and runs a background worker that
drains the change queue (debounced) and performs a periodic hash-scan safety
net, all gated by the resource governor.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from brain import __version__
from brain.config.config_loader import load_config
from brain.core.db.database import Database
from brain.core.db.repositories.change_queue_repository import (
    PRIORITY_HASH_SCAN,
    ChangeQueueRepository,
)
from brain.core.db.repositories.chunk_repository import ChunkRepository
from brain.core.db.repositories.dependency_repository import DependencyRepository
from brain.core.db.repositories.file_repository import FileRepository
from brain.core.db.repositories.repo_state_repository import RepoStateRepository
from brain.core.db.repositories.symbol_repository import SymbolRepository
from brain.core.embeddings.embedding_provider import get_embedding_provider
from brain.core.indexing.incremental_indexer import IncrementalIndexer
from brain.core.indexing.indexer import IndexResult, Indexer
from brain.core.repo.file_hasher import hash_file
from brain.core.repo.file_scanner import scan_repo
from brain.core.repo.git_service import GitService
from brain.core.query.query_planner import (
    LocalQueryResult,
    QueryContext,
    QueryPlanner,
)
from brain.core.repo.repo_root import detect_repo_root
from brain.core.retrieval.context_retriever import ContextRetriever, RetrievalResult
from brain.core.watch.change_queue import ChangeQueueManager
from brain.core.watch.file_watcher import FileWatcher
from brain.core.watch.resource_governor import ResourceGovernor
from brain.types.brain_types import Intent
from brain.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class AskOutcome:
    """Result of routing a question through the QueryPlanner.

    Exactly one of ``local_result`` / ``retrieval`` is populated depending on
    ``execution_path`` ("local" | "ai_required").
    """

    execution_path: str
    local_result: LocalQueryResult | None = None
    retrieval: RetrievalResult | None = None


class BrainEngine:
    def __init__(self, repo_root: str | None = None) -> None:
        self.repo_root = detect_repo_root(repo_root)
        self.config = load_config(self.repo_root)
        self.db = Database(self.repo_root)
        self.embedder = get_embedding_provider(self.config)

        self.files = FileRepository(self.db)
        self.chunks = ChunkRepository(self.db)
        self.symbols = SymbolRepository(self.db)
        self.deps = DependencyRepository(self.db)
        self.repo_state = RepoStateRepository(self.db)
        self.queue_repo = ChangeQueueRepository(self.db)
        self.git = GitService(self.repo_root)

        self.indexer = Indexer(self.repo_root, self.db, self.embedder, self.config)
        self.incremental = IncrementalIndexer(self.indexer, self.queue_repo)
        self.governor = ResourceGovernor(self.config.indexing)

        self.queue_manager = ChangeQueueManager(
            self.repo_root,
            self.queue_repo,
            self.config.indexing.debounce_ms,
            on_flush=self._on_flush,
        )
        self.watcher = FileWatcher(self.repo_root, self.queue_manager)

        self._watching = False
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self.repo_state.ensure(self.repo_root, self.git.current_branch())
        self._check_staleness()

    def _check_staleness(self) -> None:
        """Mark the index stale when an existing index was built by older code.

        Compares the *stored* build versions (never mutated here) against the
        current code versions. Only flags an actual upgrade scenario — a repo
        that was previously indexed but whose derived data is now out of date.
        Fresh, never-indexed repos are simply not yet indexed (``fresh``).
        """

        state = self.repo_state.get()
        already_indexed = bool(state and state["last_full_index_at"])
        changed = self.repo_state.detect_stale_components()
        if already_indexed and changed:
            self.repo_state.mark_stale()
            log.warning(
                "Index is out of date after upgrade (changed: %s). "
                "Run `brain index` to rebuild.",
                ", ".join(changed),
            )

    # -- operations -------------------------------------------------------
    def version(self) -> str:
        return __version__

    def run_full_index(self) -> IndexResult:
        result = self.indexer.full_index()
        # A full index authoritatively brings the entire repo up to date, so any
        # entries already in the change queue are now redundant. Clearing them
        # leaves the repo in a deterministically "fresh" state instead of
        # depending on the (governor-gated) background worker to drain them.
        self.queue_repo.clear_all()
        return result

    def retrieve_context(self, prompt: str, intent: Intent | None, include_full_diff: bool) -> RetrievalResult:
        retriever = ContextRetriever(self.repo_root, self.db, self.embedder, self.config)
        result = retriever.retrieve(prompt, intent=intent, include_full_diff=include_full_diff)
        from brain.core.retrieval.context_packer import pack

        result.markdown = pack(result)
        return result

    def ask(self, question: str, repo_path: str | None = None) -> "AskOutcome":
        """Route a question via the QueryPlanner (the single entry point).

        Returns an :class:`AskOutcome` describing whether the answer was
        produced locally or requires the client's AI pipeline. This method
        NEVER calls an AI provider.
        """

        if repo_path:
            from pathlib import Path

            if Path(repo_path).resolve() != Path(self.repo_root).resolve():
                raise ValueError(
                    f"repoPath '{repo_path}' does not match the daemon's repo "
                    f"root '{self.repo_root}'"
                )

        ctx = QueryContext(
            symbols=self.symbols,
            deps=self.deps,
            is_stale=self.repo_state.is_stale(),
        )
        plan = QueryPlanner(ctx).plan(question)
        if plan.execution_path == "local" and plan.local_result is not None:
            return AskOutcome(execution_path="local", local_result=plan.local_result)

        # AI reasoning required: build the context package for the client.
        retrieval = self.retrieve_context(question, None, False)
        return AskOutcome(execution_path="ai_required", retrieval=retrieval)

    def status(self) -> dict:
        state = self.repo_state.get()
        stale = self.repo_state.is_stale()
        stale_reason = None
        if stale:
            changed = self.repo_state.detect_stale_components()
            comps = ", ".join(changed) if changed else "schema/version"
            stale_reason = (
                f"Index built with outdated components ({comps}). "
                "Run `brain index` to rebuild."
            )
        return {
            "repo_root": self.repo_root,
            "indexed_files": self.files.count(),
            "chunks": self.chunks.count(),
            "symbols": self.symbols.count(),
            "last_full_index_at": state["last_full_index_at"] if state else None,
            "last_incremental_index_at": state["last_incremental_index_at"] if state else None,
            "pending_queue_size": self.queue_repo.pending_count(),
            "current_branch": self.git.current_branch(),
            "fresh": self.queue_repo.pending_count() == 0 and self.files.count() > 0,
            "stale": stale,
            "stale_reason": stale_reason,
        }

    def git_refresh(self) -> tuple[int, list[str]]:
        branch = self.git.current_branch()
        self.repo_state.set_branch(branch)
        changed = self.git.changed_files()
        count = self.queue_repo.enqueue_many(changed, "modified", PRIORITY_HASH_SCAN)
        self._on_flush()
        return count, changed

    def enqueue_changes(self, paths: list[str], event_type: str, priority: int | None) -> int:
        from brain.core.db.repositories.change_queue_repository import PRIORITY_USER_EDIT

        prio = priority if priority is not None else PRIORITY_USER_EDIT
        count = self.queue_repo.enqueue_many(paths, event_type, prio)
        self._on_flush()
        return count

    # -- watch lifecycle --------------------------------------------------
    def start_watch(self) -> bool:
        if self._watching:
            return True
        self._watching = self.watcher.start()
        self._stop.clear()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        return self._watching

    def stop_watch(self) -> None:
        self._stop.set()
        self.watcher.stop()
        self.queue_manager.cancel()
        self._watching = False

    def is_watching(self) -> bool:
        return self._watching

    def shutdown(self) -> None:
        self.stop_watch()
        self.db.close()

    # -- background work --------------------------------------------------
    def _on_flush(self) -> None:
        """Drain the change queue once, honoring the resource governor."""

        paused, reason = self.governor.should_pause()
        if paused:
            log.info("Indexing paused: %s", reason)
            return
        batch = self.config.indexing.batch_size_files
        sleep_ms = self.config.indexing.batch_sleep_ms
        while self.queue_repo.pending_count() > 0:
            paused, reason = self.governor.should_pause()
            if paused:
                log.info("Indexing paused mid-batch: %s", reason)
                break
            res = self.incremental.process_batch(batch, sleep_ms)
            if res.processed == 0:
                break
        self.queue_repo.clear_done()

    def _worker_loop(self) -> None:
        """Periodic hash-scan safety net (default every 10 minutes)."""

        interval = max(30, self.config.hash_scan.interval_seconds)
        next_scan = time.time() + interval
        while not self._stop.wait(5.0):
            if not self.config.hash_scan.enabled:
                continue
            if time.time() >= next_scan:
                try:
                    self._hash_scan()
                except Exception as exc:  # noqa: BLE001
                    log.warning("hash scan failed: %s", exc)
                next_scan = time.time() + interval

    def _hash_scan(self) -> None:
        paused, reason = self.governor.should_pause()
        if paused:
            log.debug("hash scan skipped: %s", reason)
            return
        log.info("Running periodic hash scan")
        scanned = scan_repo(self.repo_root)
        max_batch = self.config.hash_scan.max_files_per_batch
        enqueued = 0
        for sf in scanned:
            if enqueued >= max_batch:
                break
            stored = self.files.get_hash(sf.rel_path)
            current = hash_file(sf.path)
            if stored != current:
                self.queue_manager.enqueue_hash_scan(sf.rel_path)
                enqueued += 1
        if enqueued:
            log.info("Hash scan enqueued %d changed files", enqueued)
