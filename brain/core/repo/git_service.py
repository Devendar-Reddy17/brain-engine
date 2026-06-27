"""Git operations via subprocess.

All methods are defensive: if git is missing or the directory is not a repo,
they return safe defaults rather than raising, so indexing works in non-git
projects too.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from brain.utils.logger import get_logger

log = get_logger(__name__)


class GitService:
    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = str(repo_root)

    def _run(self, args: list[str]) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as exc:
            log.debug("git %s failed: %s", " ".join(args), exc)
            return None
        if result.returncode != 0:
            log.debug("git %s exited %d: %s", " ".join(args), result.returncode, result.stderr.strip())
            return None
        return result.stdout

    def is_git_repo(self) -> bool:
        out = self._run(["rev-parse", "--is-inside-work-tree"])
        return bool(out and out.strip() == "true")

    def current_branch(self) -> str | None:
        out = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        return out.strip() if out else None

    def diff(self, *, staged: bool = False, name_only: bool = False) -> str:
        args = ["diff"]
        if staged:
            args.append("--cached")
        if name_only:
            args.append("--name-only")
        out = self._run(args)
        return out or ""

    def diff_summary(self) -> str:
        out = self._run(["diff", "--stat"])
        return (out or "").strip()

    def changed_files(self) -> list[str]:
        """Return working-tree + staged changed file paths (relative)."""

        files: set[str] = set()
        for args in (["diff", "--name-only"], ["diff", "--cached", "--name-only"]):
            out = self._run(args)
            if out:
                files.update(line.strip() for line in out.splitlines() if line.strip())
        # Untracked files
        untracked = self._run(["ls-files", "--others", "--exclude-standard"])
        if untracked:
            files.update(line.strip() for line in untracked.splitlines() if line.strip())
        return sorted(files)

    def changed_files_between(self, ref_a: str, ref_b: str = "HEAD") -> list[str]:
        out = self._run(["diff", "--name-only", ref_a, ref_b])
        if not out:
            return []
        return sorted(line.strip() for line in out.splitlines() if line.strip())
