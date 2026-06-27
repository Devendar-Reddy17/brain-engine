"""Rules for deciding which files/directories to index.

Ignores dependency, build, VCS, and editor folders, plus binary/non-source
files. Supported source extensions are language-aware; Java is the first-class
target but common languages are recognized so the scanner is useful broadly.
"""

from __future__ import annotations

from pathlib import PurePath

# Directories that should never be scanned.
IGNORED_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        "target",
        "build",
        "dist",
        "out",
        ".git",
        ".idea",
        ".vscode",
        ".vs",
        "coverage",
        ".gradle",
        ".mvn",
        "bin",
        "obj",
        "__pycache__",
        ".pytest_cache",
        ".tmp",
        ".mypy_cache",
        ".venv",
        "venv",
        ".next",
        ".nuxt",
        ".cache",
        "vendor",
        ".brain",
        "generated",
        "gen",
    }
)

# Map of file extension -> language identifier.
LANGUAGE_BY_EXT: dict[str, str] = {
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rb": "ruby",
    ".rs": "rust",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".php": "php",
    ".scala": "scala",
    ".xml": "xml",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".properties": "properties",
    ".gradle": "gradle",
    ".sql": "sql",
}

# Files that are useful as config/context even without a code language.
CONFIG_FILENAMES: frozenset[str] = frozenset(
    {
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "application.properties",
        "application.yml",
        "application.yaml",
    }
)


def is_ignored_dir(name: str) -> bool:
    return name in IGNORED_DIRS


def detect_language(path: str) -> str | None:
    """Return a language id for a path, or None if unsupported."""

    p = PurePath(path)
    ext = p.suffix.lower()
    if ext in LANGUAGE_BY_EXT:
        return LANGUAGE_BY_EXT[ext]
    if p.name in CONFIG_FILENAMES:
        return "config"
    return None


def is_supported_file(path: str) -> bool:
    """True if the file is a source/config file we should index."""

    return detect_language(path) is not None


def path_has_ignored_component(parts: tuple[str, ...]) -> bool:
    """True if any path component is an ignored directory."""

    return any(part in IGNORED_DIRS for part in parts)
