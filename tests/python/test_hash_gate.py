from pathlib import Path

from brain.core.db.database import Database
from brain.core.db.repositories.chunk_repository import ChunkRepository
from brain.core.db.repositories.file_repository import FileRepository
from brain.core.indexing.hash_gate import HashGate


def _gate(tmp_path: Path):
    db = Database(tmp_path)
    files = FileRepository(db)
    chunks = ChunkRepository(db)
    return db, files, chunks, HashGate(files, chunks)


def test_file_changed_for_new_file(tmp_path: Path):
    _, files, _, gate = _gate(tmp_path)
    assert gate.file_changed("A.java", "hash1") is True


def test_file_unchanged_after_upsert(tmp_path: Path):
    _, files, _, gate = _gate(tmp_path)
    files.upsert(path="A.java", language="java", size_bytes=10, file_hash="hash1", last_modified_at=None)
    assert gate.file_changed("A.java", "hash1") is False
    assert gate.file_changed("A.java", "hash2") is True


def test_chunk_changed_then_unchanged(tmp_path: Path):
    _, files, chunks, gate = _gate(tmp_path)
    file_id = files.upsert(path="A.java", language="java", size_bytes=10, file_hash="h", last_modified_at=None)
    assert gate.chunk_changed("c1", "ch1") is True
    chunks.upsert(
        file_id=file_id, chunk_id="c1", symbol_name="m", symbol_type="method",
        language="java", start_line=1, end_line=2, content_hash="ch1", content="x",
    )
    assert gate.chunk_changed("c1", "ch1") is False
    assert gate.chunk_changed("c1", "ch2") is True
