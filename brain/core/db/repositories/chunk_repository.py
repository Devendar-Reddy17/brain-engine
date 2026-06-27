"""Data access for the ``chunks`` table."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from brain.core.db.database import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChunkRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(
        self,
        *,
        file_id: int,
        chunk_id: str,
        symbol_name: str | None,
        symbol_type: str | None,
        language: str | None,
        start_line: int,
        end_line: int,
        content_hash: str,
        content: str,
        embedding_id: int | None = None,
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO chunks (file_id, chunk_id, symbol_name, symbol_type,
                                    language, start_line, end_line, content_hash,
                                    content, embedding_id, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    file_id=excluded.file_id,
                    symbol_name=excluded.symbol_name,
                    symbol_type=excluded.symbol_type,
                    language=excluded.language,
                    start_line=excluded.start_line,
                    end_line=excluded.end_line,
                    content_hash=excluded.content_hash,
                    content=excluded.content,
                    embedding_id=excluded.embedding_id,
                    indexed_at=excluded.indexed_at
                """,
                (
                    file_id,
                    chunk_id,
                    symbol_name,
                    symbol_type,
                    language,
                    start_line,
                    end_line,
                    content_hash,
                    content,
                    embedding_id,
                    _now(),
                ),
            )

    def get_by_chunk_id(self, chunk_id: str) -> sqlite3.Row | None:
        return self.db.query_one("SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,))

    def content_hash(self, chunk_id: str) -> str | None:
        row = self.db.query_one(
            "SELECT content_hash FROM chunks WHERE chunk_id = ?", (chunk_id,)
        )
        return row["content_hash"] if row else None

    def set_embedding_id(self, chunk_id: str, embedding_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE chunks SET embedding_id = ? WHERE chunk_id = ?",
                (embedding_id, chunk_id),
            )

    def list_by_file(self, file_id: int) -> list[sqlite3.Row]:
        return self.db.query_all("SELECT * FROM chunks WHERE file_id = ?", (file_id,))

    def list_all(self) -> list[sqlite3.Row]:
        return self.db.query_all("SELECT * FROM chunks")

    def delete_by_file(self, file_id: int) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))

    def delete_missing(self, file_id: int, keep_chunk_ids: list[str]) -> None:
        """Delete chunks for a file whose chunk_id is not in ``keep_chunk_ids``."""

        with self.db.transaction() as conn:
            if not keep_chunk_ids:
                conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
                return
            placeholders = ",".join("?" for _ in keep_chunk_ids)
            conn.execute(
                f"DELETE FROM chunks WHERE file_id = ? AND chunk_id NOT IN ({placeholders})",
                (file_id, *keep_chunk_ids),
            )

    def search_content(self, term: str, limit: int = 20) -> list[sqlite3.Row]:
        like = f"%{term}%"
        return self.db.query_all(
            """
            SELECT c.*, f.path AS file_path
            FROM chunks c JOIN files f ON f.id = c.file_id
            WHERE f.is_deleted = 0
              AND (c.content LIKE ? OR c.symbol_name LIKE ?)
            LIMIT ?
            """,
            (like, like, limit),
        )

    def count(self) -> int:
        row = self.db.query_one("SELECT COUNT(*) AS c FROM chunks")
        return int(row["c"]) if row else 0
