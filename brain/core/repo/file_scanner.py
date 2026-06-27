"""Scan a repository for supported source/config files.

Walks the tree, pruning ignored directories, and yields metadata for each
supported file. Designed to be cheap: it does not read file contents (only
``os.stat``); hashing/parsing happen later behind the hash gate.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from brain.core.repo.ignore_rules import detect_language, is_ignored_dir, is_supported_file


@dataclass(frozen=True)
class ScannedFile:
    path: str          # absolute path
    rel_path: str      # path relative to repo root (forward slashes)
    language: str
    size_bytes: int
    last_modified_at: str  # ISO 8601


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def scan_repo(repo_root: str | Path) -> list[ScannedFile]:
    """Return all supported files under ``repo_root`` (ignored dirs pruned)."""

    root = Path(repo_root).resolve()
    results: list[ScannedFile] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in place so os.walk skips them.
        dirnames[:] = [d for d in dirnames if not is_ignored_dir(d)]

        for filename in filenames:
            abs_path = Path(dirpath) / filename
            if not is_supported_file(filename):
                continue
            language = detect_language(filename)
            if language is None:
                continue
            try:
                stat = abs_path.stat()
            except OSError:
                continue
            from datetime import datetime, timezone

            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            results.append(
                ScannedFile(
                    path=str(abs_path),
                    rel_path=_rel(abs_path, root),
                    language=language,
                    size_bytes=stat.st_size,
                    last_modified_at=mtime,
                )
            )

    return results
