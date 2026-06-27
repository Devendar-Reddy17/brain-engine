"""Hash gate: skip unnecessary parsing and embedding work.

Two levels:
  * file level  - if the file hash matches the stored hash, skip the whole file.
  * chunk level - if a chunk's content hash matches the stored hash, skip
                  re-embedding (and reuse the existing embedding id).
"""

from __future__ import annotations

from brain.core.db.repositories.chunk_repository import ChunkRepository
from brain.core.db.repositories.file_repository import FileRepository


class HashGate:
    def __init__(self, files: FileRepository, chunks: ChunkRepository) -> None:
        self.files = files
        self.chunks = chunks

    def file_changed(self, rel_path: str, current_hash: str) -> bool:
        """True if the file is new or its hash differs from the stored hash."""

        stored = self.files.get_hash(rel_path)
        return stored != current_hash

    def chunk_changed(self, chunk_id: str, content_hash: str) -> bool:
        """True if the chunk is new or its content hash differs."""

        stored = self.chunks.content_hash(chunk_id)
        return stored != content_hash
