from pathlib import Path

from brain.core.db.database import Database
from brain.core.db.repositories.change_queue_repository import (
    PRIORITY_HASH_SCAN,
    ChangeQueueRepository,
)


def _queue(tmp_path: Path) -> ChangeQueueRepository:
    return ChangeQueueRepository(Database(tmp_path))


def test_clear_all_removes_pending_and_processing(tmp_path: Path):
    queue = _queue(tmp_path)
    queue.enqueue_many(["A.java", "B.java", "C.java"], "modified", PRIORITY_HASH_SCAN)
    # Move one entry into the 'processing' state to ensure it is cleared too.
    queue.claim_batch(1)
    assert queue.pending_count() == 3

    removed = queue.clear_all()

    assert removed == 3
    assert queue.pending_count() == 0


def test_clear_all_on_empty_queue_is_noop(tmp_path: Path):
    queue = _queue(tmp_path)
    assert queue.clear_all() == 0
    assert queue.pending_count() == 0
