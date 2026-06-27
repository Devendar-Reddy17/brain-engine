"""Filesystem watcher built on watchdog.

Translates created/modified/deleted/moved events for supported files into
change-queue entries (user-edit priority). Ignored directories are pruned. If
watchdog is unavailable the watcher is a no-op (the periodic hash scan remains
the safety net).
"""

from __future__ import annotations

from pathlib import Path

from brain.core.repo.ignore_rules import is_supported_file, path_has_ignored_component
from brain.core.watch.change_queue import ChangeQueueManager
from brain.utils.logger import get_logger

log = get_logger(__name__)

try:
    from watchdog.events import FileSystemEventHandler  # type: ignore
    from watchdog.observers import Observer  # type: ignore
    _HAS_WATCHDOG = True
except Exception:  # pragma: no cover
    FileSystemEventHandler = object  # type: ignore
    Observer = None  # type: ignore
    _HAS_WATCHDOG = False


class _Handler(FileSystemEventHandler):  # type: ignore[misc]
    def __init__(self, queue: ChangeQueueManager) -> None:
        self.queue = queue

    def _relevant(self, path: str) -> bool:
        parts = Path(path).parts
        if path_has_ignored_component(parts):
            return False
        return is_supported_file(path)

    def on_created(self, event) -> None:
        if not event.is_directory and self._relevant(event.src_path):
            self.queue.enqueue_user_edit(event.src_path, "created")

    def on_modified(self, event) -> None:
        if not event.is_directory and self._relevant(event.src_path):
            self.queue.enqueue_user_edit(event.src_path, "modified")

    def on_deleted(self, event) -> None:
        if not event.is_directory and self._relevant(event.src_path):
            self.queue.enqueue_user_edit(event.src_path, "deleted")

    def on_moved(self, event) -> None:
        if event.is_directory:
            return
        if self._relevant(event.src_path):
            self.queue.enqueue_user_edit(event.src_path, "deleted")
        if self._relevant(event.dest_path):
            self.queue.enqueue_user_edit(event.dest_path, "renamed")


class FileWatcher:
    def __init__(self, repo_root: str, queue: ChangeQueueManager) -> None:
        self.repo_root = repo_root
        self.queue = queue
        self._observer = None

    def start(self) -> bool:
        if not _HAS_WATCHDOG:
            log.warning("watchdog not installed; file watching disabled (hash scan still active)")
            return False
        self._observer = Observer()
        self._observer.schedule(_Handler(self.queue), self.repo_root, recursive=True)
        self._observer.daemon = True
        self._observer.start()
        log.info("File watcher started on %s", self.repo_root)
        return True

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
