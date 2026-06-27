"""Detect the repository root.

Detection walks up from a starting directory looking for a ``.git`` directory
or other well-known project markers (``pom.xml``, ``build.gradle``, ``.brain``).
Falls back to the starting directory if no marker is found.
"""

from __future__ import annotations

from pathlib import Path

from brain.utils.errors import RepoNotFoundError

_MARKERS = (
    ".git",
    ".brain",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "package.json",
)


def detect_repo_root(start: str | Path | None = None, *, strict: bool = False) -> str:
    """Detect repo root by walking up from ``start`` (defaults to cwd).

    If ``strict`` is True and no marker is found, raises RepoNotFoundError.
    Otherwise returns the absolute ``start`` directory.
    """

    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for directory in [current, *current.parents]:
        for marker in _MARKERS:
            if (directory / marker).exists():
                return str(directory)

    if strict:
        raise RepoNotFoundError(
            f"Could not detect a repository root from {current}",
            detail="No .git, .brain, pom.xml, build.gradle or package.json found.",
        )
    return str(current)
