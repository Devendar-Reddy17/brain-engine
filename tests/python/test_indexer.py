"""Tests for the full indexer's hash-gate and stale-rebuild behavior."""

from pathlib import Path

from brain.config.default_config import default_config
from brain.core.db.database import Database
from brain.core.embeddings.embedding_provider import get_embedding_provider
from brain.core.indexing.indexer import Indexer

_JAVA_SOURCE = """\
public class Foo {
    public void bar() {
        System.out.println("hi");
    }
}
"""


def _indexer(repo_root: Path) -> Indexer:
    (repo_root / "Foo.java").write_text(_JAVA_SOURCE, encoding="utf-8")
    config = default_config()
    db = Database(repo_root)
    embedder = get_embedding_provider(config)
    return Indexer(str(repo_root), db, embedder, config)


def test_full_index_hash_gate_skips_unchanged(tmp_path: Path):
    indexer = _indexer(tmp_path)

    first = indexer.full_index()
    assert first.files_indexed == 1
    assert first.forced is False

    # Nothing changed on disk: the hash gate must skip the file on a re-index.
    second = indexer.full_index()
    assert second.files_indexed == 0
    assert second.files_skipped == 1
    assert second.forced is False


def test_stale_index_forces_rebuild_despite_unchanged_hash(tmp_path: Path):
    indexer = _indexer(tmp_path)
    indexer.full_index()

    # Simulate an upgrade: derived data is now outdated even though the file
    # contents (and therefore hashes) are identical.
    indexer.repo_state.mark_stale()
    assert indexer.repo_state.is_stale() is True

    forced = indexer.full_index()

    # The forced rebuild must re-index the file even though its hash is unchanged
    assert forced.forced is True
    assert forced.files_indexed == 1
    assert forced.files_skipped == 0
    # ...and a successful full index clears the stale flag.
    assert indexer.repo_state.is_stale() is False
    # Totals reflect the authoritative DB contents, not just this run.
    assert forced.total_files == 1
    assert forced.total_chunks >= 1
    assert forced.total_symbols >= 1


def test_stale_from_version_mismatch_forces_rebuild(tmp_path: Path, monkeypatch):
    indexer = _indexer(tmp_path)
    indexer.full_index()

    # A non-stale re-index would normally skip everything.
    assert indexer.repo_state.is_stale() is False

    # Bump the chunker version as code would after a chunking change; the stored
    # version now mismatches, so detect_stale_components() flags the repo stale.
    import brain.core.versions as versions

    monkeypatch.setattr(versions, "CHUNKER_VERSION", versions.CHUNKER_VERSION + 1)
    assert "chunker" in indexer.repo_state.detect_stale_components()

    forced = indexer.full_index()
    assert forced.forced is True
    assert forced.files_indexed == 1
    # After the rebuild stored versions match again -> no longer stale.
    assert indexer.repo_state.detect_stale_components() == []


def test_full_index_removes_files_no_longer_scanned(tmp_path: Path):
    indexer = _indexer(tmp_path)

    # Simulate data from an older scan before .tmp was ignored.
    indexer.files.upsert(
        path=".tmp/Ignored.java",
        language="java",
        size_bytes=23,
        file_hash="legacy",
        last_modified_at=None,
    )
    assert indexer.files.count() == 1

    result = indexer.full_index()

    assert result.total_files == 1
    assert indexer.files.get_by_path(".tmp/Ignored.java")["is_deleted"] == 1
    assert all(".tmp/" not in row["path"] for row in indexer.files.list_active())
