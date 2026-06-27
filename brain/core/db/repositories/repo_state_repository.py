"""Data access for the singleton ``repo_state`` row."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from brain.core.db.database import Database
from brain.core.db.schema import SCHEMA_VERSION
from brain.core.versions import current_component_versions

_COMPONENT_KEYS = (
    "parser_version",
    "tagger_version",
    "chunker_version",
    "embedding_version",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RepoStateRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def ensure(self, repo_root: str, current_branch: str | None) -> None:
        """Ensure the singleton row exists; update branch/root only.

        IMPORTANT: this does NOT touch the stored component versions. Those
        represent the versions used to build the *current* index and are only
        written by :meth:`set_versions` after a successful full index.
        """

        with self.db.transaction() as conn:
            existing = conn.execute("SELECT id FROM repo_state WHERE id = 1").fetchone()
            if existing:
                conn.execute(
                    "UPDATE repo_state SET repo_root = ?, current_branch = ?, schema_version = ? WHERE id = 1",
                    (repo_root, current_branch, SCHEMA_VERSION),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO repo_state (id, repo_root, current_branch, schema_version)
                    VALUES (1, ?, ?, ?)
                    """,
                    (repo_root, current_branch, SCHEMA_VERSION),
                )

    def get(self) -> sqlite3.Row | None:
        return self.db.query_one("SELECT * FROM repo_state WHERE id = 1")

    def set_branch(self, branch: str | None) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE repo_state SET current_branch = ? WHERE id = 1", (branch,))

    def mark_full_index(self) -> None:
        ts = _now()
        versions = current_component_versions()
        with self.db.transaction() as conn:
            # A successful full index brings derived data up to date with the
            # current code, so record the build versions and clear staleness.
            conn.execute(
                """
                UPDATE repo_state SET
                    last_full_index_at = ?,
                    last_incremental_index_at = ?,
                    schema_version = ?,
                    parser_version = ?,
                    tagger_version = ?,
                    chunker_version = ?,
                    embedding_version = ?,
                    stale = 0
                WHERE id = 1
                """,
                (
                    ts,
                    ts,
                    SCHEMA_VERSION,
                    versions["parser_version"],
                    versions["tagger_version"],
                    versions["chunker_version"],
                    versions["embedding_version"],
                ),
            )

    def get_versions(self) -> dict[str, int | None]:
        """Return the component versions used to build the current index."""

        row = self.get()
        if row is None:
            return {key: None for key in _COMPONENT_KEYS}
        return {key: row[key] for key in _COMPONENT_KEYS}

    def set_versions(self, versions: dict[str, int]) -> None:
        """Persist build component versions (called after a successful index)."""

        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE repo_state SET
                    parser_version = ?,
                    tagger_version = ?,
                    chunker_version = ?,
                    embedding_version = ?
                WHERE id = 1
                """,
                (
                    versions["parser_version"],
                    versions["tagger_version"],
                    versions["chunker_version"],
                    versions["embedding_version"],
                ),
            )

    def is_stale(self) -> bool:
        row = self.get()
        return bool(row["stale"]) if row is not None else False

    def mark_stale(self) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE repo_state SET stale = 1 WHERE id = 1")

    def clear_stale(self) -> None:
        with self.db.transaction() as conn:
            conn.execute("UPDATE repo_state SET stale = 0 WHERE id = 1")

    def detect_stale_components(self) -> list[str]:
        """Return component names whose stored version differs from current code.

        A stored value of ``None`` (e.g. just-migrated DB) counts as stale.
        Future hook: the background worker can use this to enqueue only the
        affected files for reindex instead of forcing a full manual reindex.
        TODO: add per-file component-version columns to ``files`` so background
        reindex can reprocess only affected files (repo-level is enough now).
        """

        stored = self.get_versions()
        current = current_component_versions()
        changed: list[str] = []
        for key, current_value in current.items():
            if stored.get(key) != current_value:
                changed.append(key.removesuffix("_version"))
        # Schema is tracked separately but also implies staleness.
        row = self.get()
        if row is not None and row["schema_version"] != SCHEMA_VERSION:
            changed.append("schema")
        return changed

    def mark_incremental_index(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE repo_state SET last_incremental_index_at = ? WHERE id = 1",
                (_now(),),
            )
