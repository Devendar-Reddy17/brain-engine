"""SQLite schema for the brain metadata store (``.brain/brain.db``).

Tables: repo_state, files, chunks, symbols, dependencies, embeddings,
change_queue. All DDL is idempotent (``IF NOT EXISTS``).

Column-add migrations (for DBs created by an older schema version) are applied
idempotently in :func:`apply_schema` by checking ``PRAGMA table_info`` before
issuing ``ALTER TABLE ... ADD COLUMN``.
"""

from __future__ import annotations

import sqlite3

# Re-exported from brain.core.versions to keep a single source of truth while
# avoiding a circular import at module load (versions has no dependencies).
from brain.core.versions import SCHEMA_VERSION

_DDL_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS repo_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        repo_root TEXT NOT NULL,
        current_branch TEXT,
        last_full_index_at TEXT,
        last_incremental_index_at TEXT,
        schema_version INTEGER NOT NULL,
        parser_version INTEGER,
        tagger_version INTEGER,
        chunker_version INTEGER,
        embedding_version INTEGER,
        stale INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT NOT NULL UNIQUE,
        language TEXT,
        size_bytes INTEGER,
        file_hash TEXT,
        last_modified_at TEXT,
        indexed_at TEXT,
        is_deleted INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER NOT NULL,
        chunk_id TEXT NOT NULL UNIQUE,
        symbol_name TEXT,
        symbol_type TEXT,
        language TEXT,
        start_line INTEGER,
        end_line INTEGER,
        content_hash TEXT,
        content TEXT,
        embedding_id INTEGER,
        indexed_at TEXT,
        FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS symbols (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        kind TEXT,
        parent_symbol TEXT,
        start_line INTEGER,
        end_line INTEGER,
        signature TEXT,
        visibility TEXT,
        annotations_json TEXT,
        tags_json TEXT,
        metadata_json TEXT,
        FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dependencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_symbol_id INTEGER,
        target_symbol_name TEXT,
        target_file_path TEXT,
        edge_type TEXT NOT NULL,
        FOREIGN KEY (source_symbol_id) REFERENCES symbols (id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS embeddings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chunk_id TEXT NOT NULL,
        vector_json TEXT NOT NULL,
        model TEXT NOT NULL,
        created_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS change_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT NOT NULL,
        event_type TEXT NOT NULL,
        priority INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT,
        processed_at TEXT
    )
    """,
    # Indexes for hot lookup paths
    "CREATE INDEX IF NOT EXISTS idx_files_path ON files (path)",
    "CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON chunks (file_id)",
    "CREATE INDEX IF NOT EXISTS idx_chunks_symbol_name ON chunks (symbol_name)",
    "CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols (file_id)",
    "CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols (name)",
    "CREATE INDEX IF NOT EXISTS idx_deps_source ON dependencies (source_symbol_id)",
    "CREATE INDEX IF NOT EXISTS idx_deps_target_name ON dependencies (target_symbol_name)",
    "CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON embeddings (chunk_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_change_queue_path ON change_queue (file_path)",
]


# (table, column, column_def) tuples applied idempotently for DBs created by an
# older schema version. New installs already get these via the CREATE TABLE DDL.
_COLUMN_MIGRATIONS: list[tuple[str, str, str]] = [
    ("symbols", "annotations_json", "TEXT"),
    ("symbols", "tags_json", "TEXT"),
    ("symbols", "metadata_json", "TEXT"),
    ("repo_state", "parser_version", "INTEGER"),
    ("repo_state", "tagger_version", "INTEGER"),
    ("repo_state", "chunker_version", "INTEGER"),
    ("repo_state", "embedding_version", "INTEGER"),
    ("repo_state", "stale", "INTEGER NOT NULL DEFAULT 0"),
]


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def apply_schema(conn: sqlite3.Connection) -> None:
    """Create all tables/indexes and apply idempotent column migrations."""

    cur = conn.cursor()
    for statement in _DDL_STATEMENTS:
        cur.execute(statement)

    # Idempotent ADD COLUMN migrations for pre-existing tables.
    for table, column, column_def in _COLUMN_MIGRATIONS:
        if column not in _existing_columns(conn, table):
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")

    conn.commit()
