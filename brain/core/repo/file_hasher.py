"""Deterministic content hashing for files and chunks.

Uses SHA-256. File hashing is streamed so large files do not load fully into
memory. Content hashing is used by the hash gate to skip unchanged work.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_BYTES = 65536


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_text(text: str) -> str:
    """Hash text content (UTF-8). Used for chunk content hashes."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_file(path: str | Path) -> str:
    """Stream-hash a file's bytes with SHA-256."""

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()
