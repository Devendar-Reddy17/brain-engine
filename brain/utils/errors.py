"""Typed errors for the brain daemon with helpful messages."""

from __future__ import annotations


class BrainError(Exception):
    """Base class for all brain errors."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class RepoNotFoundError(BrainError):
    """Raised when a repository root cannot be detected."""


class ConfigError(BrainError):
    """Raised when configuration is invalid or cannot be loaded."""


class DatabaseError(BrainError):
    """Raised on database failures."""


class ParserError(BrainError):
    """Raised when a source file cannot be parsed."""


class NotIndexedError(BrainError):
    """Raised when an operation requires an index that does not exist yet."""


class PatchSafetyError(BrainError):
    """Raised when a patch references unsafe paths."""
