"""Data access for the persisted ``change_queue`` table.

The queue deduplicates by file path (a unique index on ``file_path``) and
prioritizes higher-priority events. Persistence means a daemon restart does not
lose pending work.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from brain.core.db.database import Database

# Priority constants (higher = processed sooner)
PRIORITY_USER_EDIT = 30
PRIORITY_GIT = 20
PRIORITY_HASH_SCAN = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChangeQueueRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def enqueue(self, file_path: str, event_type: str, priority: int) -> None:
        """Add or upsert a pending change, keeping the highest priority seen."""

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO change_queue (file_path, event_type, priority, status, created_at)
                VALUES (?, ?, ?, 'pending', ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    event_type=excluded.event_type,
                    priority=MAX(change_queue.priority, excluded.priority),
                    status='pending',
                    created_at=excluded.created_at,
                    processed_at=NULL
                """,
                (file_path, event_type, priority, _now()),
            )

    def enqueue_many(self, paths: list[str], event_type: str, priority: int) -> int:
        count = 0
        for path in paths:
            self.enqueue(path, event_type, priority)
            count += 1
        return count

    def claim_batch(self, limit: int) -> list[sqlite3.Row]:
        """Mark a batch of pending items as processing and return them."""

        with self.db.transaction() as conn:
            rows = conn.execute(
                """
                SELECT * FROM change_queue
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            ids = [r["id"] for r in rows]
            for qid in ids:
                conn.execute(
                    "UPDATE change_queue SET status = 'processing' WHERE id = ?",
                    (qid,),
                )
        return rows

    def mark_processed(self, queue_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE change_queue SET status = 'done', processed_at = ? WHERE id = ?",
                (_now(), queue_id),
            )

    def requeue(self, queue_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE change_queue SET status = 'pending' WHERE id = ?", (queue_id,)
            )

    def clear_done(self) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM change_queue WHERE status = 'done'")

    def clear_all(self) -> int:
        """Remove every queued change. Used after a full index, which brings the
        entire repo up to date and makes any pending entries redundant."""

        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM change_queue")
            return int(cur.rowcount or 0)

    def pending_count(self) -> int:
        row = self.db.query_one(
            "SELECT COUNT(*) AS c FROM change_queue WHERE status IN ('pending', 'processing')"
        )
        return int(row["c"]) if row else 0
