from pathlib import Path

from brain.core.db.database import Database
from brain.core.db.repositories.chunk_repository import ChunkRepository
from brain.core.db.repositories.file_repository import FileRepository
from brain.core.retrieval.token_savings_estimator import (
    ApproxTokenEstimator,
    TokenSavingsEstimator,
)


def test_approx_estimator_chars_div_4():
    est = ApproxTokenEstimator()
    assert est.count("") == 0
    assert est.count("abcd") == 1
    assert est.count("a" * 40) == 10


def test_calculate_reduction():
    db = Database(Path("."))  # repo root with existing .brain
    est = TokenSavingsEstimator(FileRepository(db), ChunkRepository(db))
    assert est.calculate_reduction(0, 100) == 0.0
    assert est.calculate_reduction(1000, 100) == 90.0
    assert est.calculate_reduction(1000, 0) == 100.0


def test_estimate_context_tokens_sums_chunks(tmp_path: Path):
    db = Database(tmp_path)
    est = TokenSavingsEstimator(FileRepository(db), ChunkRepository(db))
    total = est.estimate_context_tokens(["a" * 40, "b" * 40])
    assert total == 20


def test_build_summary_shape(tmp_path: Path):
    db = Database(tmp_path)
    est = TokenSavingsEstimator(FileRepository(db), ChunkRepository(db))
    summary = est.build_summary(425000, 18200, 95.7)
    assert summary == {
        "repoTokens": 425000,
        "contextTokens": 18200,
        "reductionPercentage": 95.7,
    }


def test_estimate_repo_tokens_uses_file_sizes(tmp_path: Path):
    db = Database(tmp_path)
    files = FileRepository(db)
    files.upsert(path="A.java", language="java", size_bytes=400, file_hash="h", last_modified_at=None)
    files.upsert(path="B.java", language="java", size_bytes=400, file_hash="h", last_modified_at=None)
    est = TokenSavingsEstimator(files, ChunkRepository(db))
    # 800 bytes / 4 chars-per-token = 200 tokens
    assert est.estimate_repo_tokens(str(tmp_path)) == 200
