"""Data access for the ``dependencies`` table (the symbol dependency graph)."""

from __future__ import annotations

import sqlite3

from brain.core.db.database import Database


class DependencyRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def replace_for_sources(self, source_symbol_ids: list[int], edges: list[dict]) -> None:
        """Replace all edges originating from the given source symbol ids.

        ``edges`` items: source_symbol_id, target_symbol_name, target_file_path, edge_type.
        """

        with self.db.transaction() as conn:
            for sid in source_symbol_ids:
                conn.execute(
                    "DELETE FROM dependencies WHERE source_symbol_id = ?", (sid,)
                )
            for edge in edges:
                conn.execute(
                    """
                    INSERT INTO dependencies (source_symbol_id, target_symbol_name,
                                              target_file_path, edge_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        edge.get("source_symbol_id"),
                        edge.get("target_symbol_name"),
                        edge.get("target_file_path"),
                        edge.get("edge_type"),
                    ),
                )

    def callees_of(self, source_symbol_id: int) -> list[sqlite3.Row]:
        return self.db.query_all(
            "SELECT * FROM dependencies WHERE source_symbol_id = ?",
            (source_symbol_id,),
        )

    def callers_of(self, target_symbol_name: str) -> list[sqlite3.Row]:
        return self.db.query_all(
            """
            SELECT d.*, s.name AS source_name, f.path AS source_file
            FROM dependencies d
            JOIN symbols s ON s.id = d.source_symbol_id
            JOIN files f ON f.id = s.file_id
            WHERE d.target_symbol_name = ?
            """,
            (target_symbol_name,),
        )

    def by_edge_type(self, target_symbol_name: str, edge_type: str) -> list[sqlite3.Row]:
        return self.db.query_all(
            """
            SELECT * FROM dependencies
            WHERE target_symbol_name = ? AND edge_type = ?
            """,
            (target_symbol_name, edge_type),
        )

    def list_by_edge_type(self, edge_type: str, limit: int = 500) -> list[sqlite3.Row]:
        """All edges of a given type, joined to the source symbol + file.

        Used by local queries such as "show all routes" (``routes_to``),
        "classes extending X" (``extends``), "classes implementing X"
        (``implements``), and "imports of a file" (``imports``).
        """

        return self.db.query_all(
            """
            SELECT d.*, s.name AS source_name, s.kind AS source_kind,
                   s.start_line AS source_start_line, s.end_line AS source_end_line,
                   f.path AS source_file
            FROM dependencies d
            JOIN symbols s ON s.id = d.source_symbol_id
            JOIN files f ON f.id = s.file_id
            WHERE d.edge_type = ? AND f.is_deleted = 0
            ORDER BY f.path, s.start_line
            LIMIT ?
            """,
            (edge_type, limit),
        )

    def imports_for_file(self, file_path_like: str, limit: int = 500) -> list[sqlite3.Row]:
        return self.db.query_all(
            """
            SELECT d.target_symbol_name AS name, f.path AS source_file
            FROM dependencies d
            JOIN symbols s ON s.id = d.source_symbol_id
            JOIN files f ON f.id = s.file_id
            WHERE d.edge_type = 'imports' AND f.is_deleted = 0 AND f.path LIKE ?
            ORDER BY d.target_symbol_name
            LIMIT ?
            """,
            (f"%{file_path_like}%", limit),
        )

    def count(self) -> int:
        row = self.db.query_one("SELECT COUNT(*) AS c FROM dependencies")
        return int(row["c"]) if row else 0
