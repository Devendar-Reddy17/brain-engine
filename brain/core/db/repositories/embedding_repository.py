"""Data access for the ``embeddings`` table."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from brain.core.db.database import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EmbeddingRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, *, chunk_id: str, vector: list[float], model: str) -> int:
        """Insert or replace the embedding for a chunk; returns the embedding id."""

        vector_json = json.dumps(vector)
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM embeddings WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE embeddings SET vector_json = ?, model = ?, created_at = ? WHERE id = ?",
                    (vector_json, model, _now(), existing["id"]),
                )
                return int(existing["id"])
            cur = conn.execute(
                """
                INSERT INTO embeddings (chunk_id, vector_json, model, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (chunk_id, vector_json, model, _now()),
            )
            return int(cur.lastrowid)

    def get_vector(self, chunk_id: str) -> list[float] | None:
        row = self.db.query_one(
            "SELECT vector_json FROM embeddings WHERE chunk_id = ?", (chunk_id,)
        )
        if not row:
            return None
        return json.loads(row["vector_json"])

    def all_vectors(self) -> list[tuple[str, list[float]]]:
        rows = self.db.query_all("SELECT chunk_id, vector_json FROM embeddings")
        return [(r["chunk_id"], json.loads(r["vector_json"])) for r in rows]

    def delete_for_chunk(self, chunk_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM embeddings WHERE chunk_id = ?", (chunk_id,))

    def count(self) -> int:
        row = self.db.query_one("SELECT COUNT(*) AS c FROM embeddings")
        return int(row["c"]) if row else 0
