"""Extract symbols from source via the language parser.

Thin wrapper that runs the appropriate :class:`Parser` and converts the parsed
symbols into the dict shape expected by ``SymbolRepository``. The full
:class:`ParseResult` is also returned for chunking and dependency building.
"""

from __future__ import annotations

import json

from brain.core.parsing import tagging
from brain.core.parsing.parser import ParseResult, get_parser


def extract(source: str, rel_path: str, language: str) -> ParseResult:
    """Parse ``source`` and return the full ParseResult with tags applied.

    Tag derivation happens here — in one shared place — so the individual
    parsers stay tag-agnostic and only populate raw annotations/route/is_test.
    """

    parser = get_parser(language)
    result = parser.parse(source, rel_path)
    for sym in result.symbols:
        # Populate the neutral provenance fields so taggers can dispatch by
        # language and reason about module/file conventions, then derive tags.
        sym.language = result.language
        if not sym.file_path:
            sym.file_path = rel_path
        sym.tags = tagging.derive_tags(sym, result.language)
    return result


def to_symbol_rows(result: ParseResult) -> list[dict]:
    """Convert ParsedSymbols to ``symbols`` table row dicts."""

    rows: list[dict] = []
    for sym in result.symbols:
        rows.append(
            {
                "name": sym.name,
                "kind": sym.kind,
                "parent_symbol": sym.parent_symbol,
                "start_line": sym.start_line,
                "end_line": sym.end_line,
                "signature": sym.signature,
                "visibility": sym.visibility,
                "annotations_json": json.dumps(sym.annotations),
                "tags_json": json.dumps(sym.tags),
                "metadata_json": json.dumps(sym.framework_metadata) if sym.framework_metadata else None,
            }
        )
    return rows
