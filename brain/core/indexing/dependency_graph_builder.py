"""Build dependency-graph edges from a parsed file.

Edge types: imports, calls, extends, implements, references, tested_by,
configures, routes_to. Edges originate from a concrete symbol id (resolved via
the per-file ``name -> symbol_id`` map produced when symbols are persisted).
"""

from __future__ import annotations

from brain.core.parsing import spring
from brain.core.parsing.parser import ParseResult

_TYPE_KINDS = {"class", "interface", "enum"}
_METHOD_KINDS = {"method", "function", "constructor", "route", "test"}


def build_edges(result: ParseResult, name_to_id: dict[str, int]) -> tuple[list[int], list[dict]]:
    """Return (source_symbol_ids, edges) for persistence.

    ``source_symbol_ids`` lists every symbol id that owns edges so the repository
    can clear stale edges before inserting the new set.
    """

    edges: list[dict] = []
    source_ids: set[int] = set()

    def add(source_name: str, target_name: str, edge_type: str, target_file: str | None = None) -> None:
        sid = name_to_id.get(source_name)
        if sid is None or not target_name:
            return
        source_ids.add(sid)
        edges.append(
            {
                "source_symbol_id": sid,
                "target_symbol_name": target_name,
                "target_file_path": target_file,
                "edge_type": edge_type,
            }
        )

    # Primary type in the file carries the import edges.
    primary_type = next((s for s in result.symbols if s.kind in _TYPE_KINDS), None)

    for sym in result.symbols:
        if sym.kind in _TYPE_KINDS:
            for parent in sym.extends:
                add(sym.name, parent, "extends")
            for iface in sym.implements:
                add(sym.name, iface, "implements")
            # @Configuration classes "configure" their beans.
            if any(spring.normalize_annotation(a) == "Configuration" for a in sym.annotations):
                for member in result.symbols:
                    if member.parent_symbol == sym.name and "Bean" in [
                        spring.normalize_annotation(a) for a in member.annotations
                    ]:
                        add(sym.name, member.name, "configures")

        elif sym.kind in _METHOD_KINDS:
            for callee in sym.calls:
                add(sym.name, callee, "calls")
            if sym.is_test:
                for callee in sym.calls:
                    add(sym.name, callee, "tested_by")
            if sym.route:
                add(sym.name, sym.route, "routes_to")

    # Import edges attached to the primary type (or package symbol).
    import_owner = primary_type.name if primary_type else result.package
    if import_owner:
        for imported in result.imports:
            add(import_owner, imported, "imports")

    return list(source_ids), edges
