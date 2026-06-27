"""Incremental indexer that drains the persisted change queue.

Processes a batch of pending changes, re-indexing only changed files (the hash
gate skips work when content is unchanged). Deletions mark files as deleted.
Runs at low parallelism and respects batch sleeps for opportunistic indexing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from brain.core.db.repositories.change_queue_repository import ChangeQueueRepository
from brain.core.indexing.indexer import Indexer
from brain.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class IncrementalResult:
    processed: int = 0
    reindexed: int = 0
    deleted: int = 0
    chunks: int = 0
    symbols: int = 0


class IncrementalIndexer:
    def __init__(self, indexer: Indexer, queue: ChangeQueueRepository) -> None:
        self.indexer = indexer
        self.queue = queue

    def process_batch(self, limit: int, batch_sleep_ms: int = 0) -> IncrementalResult:
        result = IncrementalResult()
        rows = self.queue.claim_batch(limit)
        for row in rows:
            qid = row["id"]
            rel_path = row["file_path"]
            event = row["event_type"]
            try:
                if event == "deleted":
                    self.indexer.files.mark_deleted(rel_path)
                    result.deleted += 1
                else:
                    indexed, n_chunks, n_symbols = self.indexer.index_path(rel_path, force=True)
                    if indexed:
                        result.reindexed += 1
                        result.chunks += n_chunks
                        result.symbols += n_symbols
                self.queue.mark_processed(qid)
                result.processed += 1
            except Exception as exc:  # noqa: BLE001
                log.warning("Incremental index failed for %s: %s", rel_path, exc)
                self.queue.requeue(qid)

        if rows:
            self.indexer.repo_state.mark_incremental_index()
        if batch_sleep_ms:
            time.sleep(batch_sleep_ms / 1000.0)
        return result
