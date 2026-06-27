"""Central component version constants.

These versions describe the code that *produces* derived index data. They are
persisted alongside the index (see ``repo_state``) representing the versions
used to build the *current* index. On daemon startup the stored versions are
compared against these constants; any mismatch marks the index stale and the
user is prompted to re-run ``brain index``. Stored versions are only updated
after a successful full index.

Bump the relevant constant whenever a subsystem changes in a way that makes
previously-derived data stale:

* ``SCHEMA_VERSION``    — SQLite schema shape (tables/columns/indexes).
* ``PARSER_VERSION``    — symbol/AST extraction output.
* ``TAGGER_VERSION``    — normalized tag derivation.
* ``CHUNKER_VERSION``   — chunk boundaries/content.
* ``EMBEDDING_VERSION`` — embedding production (model/format).
"""

from __future__ import annotations

# Keep in sync with brain/core/db/schema.py SCHEMA_VERSION (re-exported there).
# v3: symbols.metadata_json added for language-agnostic framework metadata.
SCHEMA_VERSION = 3
# v2: multi-language symbol extraction (Python ast parser; language/file_path on
# symbols) in addition to Java.
PARSER_VERSION = 2
# v2: language-agnostic tagger registry (Java/Spring + Python web frameworks).
TAGGER_VERSION = 2
CHUNKER_VERSION = 1
EMBEDDING_VERSION = 1


def current_component_versions() -> dict[str, int]:
    """Return the current code component versions (excludes schema)."""

    return {
        "parser_version": PARSER_VERSION,
        "tagger_version": TAGGER_VERSION,
        "chunker_version": CHUNKER_VERSION,
        "embedding_version": EMBEDDING_VERSION,
    }
