"""Lightweight logging helpers for the brain daemon.

Log lines are prefixed with ``[Brain]`` so they are easy to identify in CLI
output and daemon logs.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

_CONFIGURED = False
_DEFAULT_LEVEL = logging.INFO


def configure_logging(level: int = _DEFAULT_LEVEL, log_file: Optional[str] = None) -> None:
    """Configure root logging once. Safe to call multiple times."""

    global _CONFIGURED
    if _CONFIGURED:
        return

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="[Brain] %(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger, configuring logging on first use."""

    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
