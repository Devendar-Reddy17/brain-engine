from pathlib import Path

from brain.core.repo.file_hasher import hash_bytes, hash_file, hash_text


def test_hash_text_is_deterministic():
    assert hash_text("hello") == hash_text("hello")
    assert hash_text("hello") != hash_text("world")


def test_hash_bytes_matches_text():
    assert hash_bytes(b"hello") == hash_text("hello")


def test_hash_file_matches_text(tmp_path: Path):
    f = tmp_path / "sample.txt"
    content = "public class A {}"
    f.write_text(content, encoding="utf-8")
    assert hash_file(f) == hash_text(content)


def test_hash_file_changes_with_content(tmp_path: Path):
    f = tmp_path / "sample.txt"
    f.write_text("one", encoding="utf-8")
    h1 = hash_file(f)
    f.write_text("two", encoding="utf-8")
    h2 = hash_file(f)
    assert h1 != h2
