"""Filesystem path helpers for the ``.brain`` workspace.

All brain runtime state lives under ``<repo_root>/.brain``:
  - ``config.yml``  user configuration
  - ``brain.db``    SQLite metadata store
  - ``patches/``    generated patches (e.g. ``latest.patch``)
  - ``daemon.log``  daemon log file
"""

from __future__ import annotations

import os
from pathlib import Path

BRAIN_DIR_NAME = ".brain"
CONFIG_FILE_NAME = "config.yml"
DB_FILE_NAME = "brain.db"
PATCHES_DIR_NAME = "patches"
LATEST_PATCH_NAME = "latest.patch"
DAEMON_LOG_NAME = "daemon.log"


def brain_dir(repo_root: str | os.PathLike[str]) -> Path:
    return Path(repo_root) / BRAIN_DIR_NAME


def config_path(repo_root: str | os.PathLike[str]) -> Path:
    return brain_dir(repo_root) / CONFIG_FILE_NAME


def db_path(repo_root: str | os.PathLike[str]) -> Path:
    return brain_dir(repo_root) / DB_FILE_NAME


def patches_dir(repo_root: str | os.PathLike[str]) -> Path:
    return brain_dir(repo_root) / PATCHES_DIR_NAME


def latest_patch_path(repo_root: str | os.PathLike[str]) -> Path:
    return patches_dir(repo_root) / LATEST_PATCH_NAME


def daemon_log_path(repo_root: str | os.PathLike[str]) -> Path:
    return brain_dir(repo_root) / DAEMON_LOG_NAME


def ensure_brain_dirs(repo_root: str | os.PathLike[str]) -> Path:
    """Create the ``.brain`` directory tree if it does not exist."""

    bdir = brain_dir(repo_root)
    bdir.mkdir(parents=True, exist_ok=True)
    patches_dir(repo_root).mkdir(parents=True, exist_ok=True)
    return bdir


def is_within(child: str | os.PathLike[str], parent: str | os.PathLike[str]) -> bool:
    """Return True if ``child`` resolves to a path inside ``parent``."""

    try:
        child_resolved = Path(child).resolve()
        parent_resolved = Path(parent).resolve()
    except (OSError, ValueError):
        return False
    return parent_resolved == child_resolved or parent_resolved in child_resolved.parents
