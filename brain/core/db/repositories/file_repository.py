"""Data access for the ``files`` table."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from brain.core.db.database import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FileRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(
        self,
        *,
        path: str,
        language: str | None,
        size_bytes: int,
        file_hash: str,
        last_modified_at: str | None,
    ) -> int:
        """Insert or update a file row by path; returns the file id."""

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO files (path, language, size_bytes, file_hash,
                                   last_modified_at, indexed_at, is_deleted)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(path) DO UPDATE SET
                    language=excluded.language,
                    size_bytes=excluded.size_bytes,
                    file_hash=excluded.file_hash,
                    last_modified_at=excluded.last_modified_at,
                    indexed_at=excluded.indexed_at,
                    is_deleted=0
                """,
                (path, language, size_bytes, file_hash, last_modified_at, _now()),
            )
            row = conn.execute("SELECT id FROM files WHERE path = ?", (path,)).fetchone()
        return int(row["id"])

    def get_by_path(self, path: str) -> sqlite3.Row | None:
        return self.db.query_one("SELECT * FROM files WHERE path = ?", (path,))

    def get_hash(self, path: str) -> str | None:
        row = self.db.query_one(
            "SELECT file_hash FROM files WHERE path = ? AND is_deleted = 0", (path,)
        )
        return row["file_hash"] if row else None

    def list_active(self) -> list[sqlite3.Row]:
        return self.db.query_all("SELECT * FROM files WHERE is_deleted = 0 ORDER BY path")

    def mark_deleted(self, path: str) -> None:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT id FROM files WHERE path = ?", (path,)).fetchone()
            if row is None:
                return
            file_id = int(row["id"])
            chunk_rows = conn.execute(
                "SELECT chunk_id FROM chunks WHERE file_id = ?", (file_id,)
            ).fetchall()
            chunk_ids = [r["chunk_id"] for r in chunk_rows]
            if chunk_ids:
                placeholders = ",".join("?" for _ in chunk_ids)
                conn.execute(
                    f"DELETE FROM embeddings WHERE chunk_id IN ({placeholders})",
                    tuple(chunk_ids),
                )
            conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
            conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
            conn.execute(
                "UPDATE files SET is_deleted = 1, indexed_at = ? WHERE path = ?",
                (_now(), path),
            )

    def count(self) -> int:
        row = self.db.query_one("SELECT COUNT(*) AS c FROM files WHERE is_deleted = 0")
        return int(row["c"]) if row else 0

    def total_size_bytes(self) -> int:
        row = self.db.query_one(
            "SELECT COALESCE(SUM(size_bytes), 0) AS s FROM files WHERE is_deleted = 0"
        )
        return int(row["s"]) if row else 0
