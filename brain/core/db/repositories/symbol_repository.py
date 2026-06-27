"""Data access for the ``symbols`` table."""

from __future__ import annotations

import sqlite3

from brain.core.db.database import Database


class SymbolRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def replace_for_file(self, file_id: int, symbols: list[dict]) -> dict[str, int]:
        """Delete existing symbols for a file and insert the new set.

        Returns a mapping of ``symbol_name`` -> inserted symbol id (last wins on
        duplicate names, which is acceptable for dependency linking).
        """

        name_to_id: dict[str, int] = {}
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))
            for sym in symbols:
                cur = conn.execute(
                    """
                    INSERT INTO symbols (file_id, name, kind, parent_symbol,
                                         start_line, end_line, signature, visibility,
                                         annotations_json, tags_json, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        file_id,
                        sym.get("name"),
                        sym.get("kind"),
                        sym.get("parent_symbol"),
                        sym.get("start_line"),
                        sym.get("end_line"),
                        sym.get("signature"),
                        sym.get("visibility"),
                        sym.get("annotations_json"),
                        sym.get("tags_json"),
                        sym.get("metadata_json"),
                    ),
                )
                name = sym.get("name")
                if name:
                    name_to_id[name] = int(cur.lastrowid)
        return name_to_id

    def list_by_file(self, file_id: int) -> list[sqlite3.Row]:
        return self.db.query_all("SELECT * FROM symbols WHERE file_id = ?", (file_id,))

    def find_by_name(self, name: str, limit: int = 20) -> list[sqlite3.Row]:
        return self.db.query_all(
            """
            SELECT s.*, f.path AS file_path
            FROM symbols s JOIN files f ON f.id = s.file_id
            WHERE f.is_deleted = 0 AND s.name = ?
            LIMIT ?
            """,
            (name, limit),
        )

    def search_by_name(self, term: str, limit: int = 20) -> list[sqlite3.Row]:
        return self.db.query_all(
            """
            SELECT s.*, f.path AS file_path
            FROM symbols s JOIN files f ON f.id = s.file_id
            WHERE f.is_deleted = 0 AND s.name LIKE ?
            LIMIT ?
            """,
            (f"%{term}%", limit),
        )

    def count(self) -> int:
        row = self.db.query_one("SELECT COUNT(*) AS c FROM symbols")
        return int(row["c"]) if row else 0

    # -- local-query accessors -------------------------------------------
    @staticmethod
    def _tag_like(tag: str) -> str:
        """JSON-delimited LIKE pattern to avoid substring false positives.

        ``tags_json`` stores a JSON array, e.g. ``["controller", "api"]``; we
        match the quoted token so ``service`` never matches ``microservice``.
        """

        return f'%"{tag}"%'

    def list_by_tag(self, tag: str, limit: int = 500) -> list[sqlite3.Row]:
        return self.db.query_all(
            """
            SELECT s.*, f.path AS file_path
            FROM symbols s JOIN files f ON f.id = s.file_id
            WHERE f.is_deleted = 0 AND s.tags_json LIKE ?
            ORDER BY s.name
            LIMIT ?
            """,
            (self._tag_like(tag), limit),
        )

    def count_by_tag(self, tag: str) -> int:
        row = self.db.query_one(
            """
            SELECT COUNT(*) AS c
            FROM symbols s JOIN files f ON f.id = s.file_id
            WHERE f.is_deleted = 0 AND s.tags_json LIKE ?
            """,
            (self._tag_like(tag),),
        )
        return int(row["c"]) if row else 0

    def list_by_kind(self, kind: str, limit: int = 500) -> list[sqlite3.Row]:
        return self.db.query_all(
            """
            SELECT s.*, f.path AS file_path
            FROM symbols s JOIN files f ON f.id = s.file_id
            WHERE f.is_deleted = 0 AND s.kind = ?
            ORDER BY s.name
            LIMIT ?
            """,
            (kind, limit),
        )

    def count_by_kind(self, kind: str) -> int:
        row = self.db.query_one(
            """
            SELECT COUNT(*) AS c
            FROM symbols s JOIN files f ON f.id = s.file_id
            WHERE f.is_deleted = 0 AND s.kind = ?
            """,
            (kind,),
        )
        return int(row["c"]) if row else 0

    def counts_by_kind(self) -> list[sqlite3.Row]:
        return self.db.query_all(
            """
            SELECT s.kind AS kind, COUNT(*) AS c
            FROM symbols s JOIN files f ON f.id = s.file_id
            WHERE f.is_deleted = 0
            GROUP BY s.kind
            ORDER BY c DESC
            """
        )

    def list_all(self, limit: int = 5000) -> list[sqlite3.Row]:
        """All live symbols joined with file paths, ordered by file then line.

        Used by the grouped-routes handler to build in-memory owner lookups
        (parent_symbol resolution + enclosing-symbol inference).
        """

        return self.db.query_all(
            """
            SELECT s.*, f.path AS file_path
            FROM symbols s JOIN files f ON f.id = s.file_id
            WHERE f.is_deleted = 0
            ORDER BY f.path, s.start_line
            LIMIT ?
            """,
            (limit,),
        )

    def list_by_parent_field(self, file_path_like: str, kind: str, limit: int = 500) -> list[sqlite3.Row]:
        return self.db.query_all(
            """
            SELECT s.*, f.path AS file_path
            FROM symbols s JOIN files f ON f.id = s.file_id
            WHERE f.is_deleted = 0 AND s.kind = ? AND f.path LIKE ?
            ORDER BY s.start_line
            LIMIT ?
            """,
            (kind, f"%{file_path_like}%", limit),
        )
