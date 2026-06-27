"""SQLite connection management for the brain metadata store.

A single :class:`Database` instance owns one connection per process. SQLite is
configured with WAL journaling and foreign keys enabled. Access is guarded by a
lock so the daemon's background indexing and request handlers can share it.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from brain.core.db.schema import SCHEMA_VERSION, apply_schema
from brain.utils.errors import DatabaseError
from brain.utils.logger import get_logger
from brain.utils.paths import db_path, ensure_brain_dirs

log = get_logger(__name__)


class Database:
    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = str(repo_root)
        ensure_brain_dirs(repo_root)
        self._db_file = str(db_path(repo_root))
        self._lock = threading.RLock()
        self._conn = self._connect()
        apply_schema(self._conn)
        log.debug("Opened brain database at %s (schema v%d)", self._db_file, SCHEMA_VERSION)

    def _connect(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(
                self._db_file,
                check_same_thread=False,
                timeout=30.0,
            )
        except sqlite3.Error as exc:  # pragma: no cover - defensive
            raise DatabaseError("Failed to open brain database", detail=str(exc)) from exc
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a block in a transaction, committing on success."""

        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchone()

    def query_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur.fetchall()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
