"""In-process change queue manager.

Wraps the persisted :class:`ChangeQueueRepository` with path normalization,
deduplication, priority assignment, and a debounce so a burst of edits triggers
a single processing pass after a quiet period.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from brain.core.db.repositories.change_queue_repository import (
    PRIORITY_GIT,
    PRIORITY_HASH_SCAN,
    PRIORITY_USER_EDIT,
    ChangeQueueRepository,
)
from brain.core.watch.debouncer import Debouncer
from brain.utils.logger import get_logger

log = get_logger(__name__)


class ChangeQueueManager:
    def __init__(
        self,
        repo_root: str,
        repository: ChangeQueueRepository,
        debounce_ms: int,
        on_flush: Callable[[], None],
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.repository = repository
        self._debouncer = Debouncer(debounce_ms, on_flush)

    def _rel(self, path: str) -> str | None:
        try:
            return Path(path).resolve().relative_to(self.repo_root).as_posix()
        except ValueError:
            return None

    def enqueue_user_edit(self, path: str, event_type: str) -> None:
        self._enqueue(path, event_type, PRIORITY_USER_EDIT)

    def enqueue_git_change(self, rel_path: str) -> None:
        self.repository.enqueue(rel_path, "modified", PRIORITY_GIT)
        self._debouncer.trigger()

    def enqueue_hash_scan(self, rel_path: str) -> None:
        self.repository.enqueue(rel_path, "modified", PRIORITY_HASH_SCAN)
        self._debouncer.trigger()

    def _enqueue(self, path: str, event_type: str, priority: int) -> None:
        rel = self._rel(path) if Path(path).is_absolute() else path
        if rel is None:
            return
        self.repository.enqueue(rel, event_type, priority)
        self._debouncer.trigger()

    def pending_count(self) -> int:
        return self.repository.pending_count()

    def cancel(self) -> None:
        self._debouncer.cancel()
