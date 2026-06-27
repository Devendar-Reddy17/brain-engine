"""Language-agnostic parser abstraction.

A :class:`Parser` turns source text into a :class:`ParseResult` containing the
package/module, imports, and a flat list of :class:`ParsedSymbol` objects.
Symbols carry *neutral* metadata (annotations/decorators, inheritance,
relationship hints, optional route and framework metadata). Parsers must NOT
decide framework stereotypes such as ``controller``/``service`` directly — that
is the job of the language taggers (see :mod:`brain.core.parsing.tagging`).

Parsers register themselves through :func:`register_parser`. The factory
:func:`get_parser` looks a language up in the registry and falls back to a
minimal no-symbol parser for unsupported languages. Adding a new language only
requires registering a parser and a tagger — no query-layer changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from brain.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class ParsedSymbol:
    name: str
    kind: str  # SymbolKind value, e.g. "class", "method", "function"
    start_line: int
    end_line: int
    parent_symbol: str | None = None
    signature: str | None = None
    visibility: str = "unknown"
    # Raw annotations (Java) / decorators (Python/TS) attached to the symbol,
    # stored verbatim (e.g. "RestController", "router.get", "app.route").
    annotations: list[str] = field(default_factory=list)
    # Inheritance: base classes (Java extends / Python bases).
    extends: list[str] = field(default_factory=list)
    # Interfaces / mixins implemented.
    implements: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    is_test: bool = False
    route: str | None = None  # e.g. "GET /users/{id}"
    # Language id this symbol was parsed from (e.g. "java", "python"). Set by
    # symbol_extractor from the ParseResult so taggers can dispatch per-language.
    language: str = ""
    # Repo-relative file path the symbol came from (populated post-parse).
    file_path: str = ""
    # Neutral, language/framework-specific metadata bag (e.g. http_method,
    # decorator name, router variable). Persisted as metadata_json. Parsers fill
    # this with raw facts; taggers interpret it. Never query-layer specific.
    framework_metadata: dict = field(default_factory=dict)
    # Normalized, language-agnostic tags (e.g. "controller", "service", "route",
    # "test", "api"). Populated post-parse by brain.core.parsing.tagging so the
    # parsers themselves stay tag-agnostic.
    tags: list[str] = field(default_factory=list)


@dataclass
class ParseResult:
    language: str
    package: str | None = None
    imports: list[str] = field(default_factory=list)
    symbols: list[ParsedSymbol] = field(default_factory=list)


class Parser(Protocol):
    language: str

    def parse(self, source: str, rel_path: str) -> ParseResult:  # pragma: no cover - protocol
        ...


# -- parser registry --------------------------------------------------------
# language id -> factory returning a Parser instance. Registering is how new
# languages plug in without touching get_parser or the query layer.
ParserFactory = Callable[[], "Parser"]
_PARSER_FACTORIES: dict[str, ParserFactory] = {}


def register_parser(language: str, factory: ParserFactory) -> None:
    """Register a parser factory for ``language`` (later calls override)."""

    _PARSER_FACTORIES[language] = factory


def _java_parser_factory() -> "Parser":
    """Java prefers tree-sitter and falls back to a regex parser on failure."""

    try:
        from brain.core.parsing.java_parser import JavaParser

        return JavaParser()
    except Exception as exc:  # tree-sitter missing or grammar load failed
        log.warning("Tree-sitter Java parser unavailable (%s); using regex fallback", exc)
        from brain.core.parsing.fallback_java_parser import FallbackJavaParser

        return FallbackJavaParser()


def _python_parser_factory() -> "Parser":
    from brain.core.parsing.python_parser import PythonParser

    return PythonParser()


def _typescript_parser_factory() -> "Parser":
    from brain.core.parsing.typescript_parser import TypeScriptParser

    return TypeScriptParser("typescript")


def _javascript_parser_factory() -> "Parser":
    from brain.core.parsing.typescript_parser import JavaScriptParser

    return JavaScriptParser()


register_parser("java", _java_parser_factory)
register_parser("python", _python_parser_factory)
register_parser("typescript", _typescript_parser_factory)
register_parser("javascript", _javascript_parser_factory)


def get_parser(language: str) -> Parser:
    """Return a parser for ``language`` from the registry.

    Unsupported languages get a minimal file-level parser (no symbols), so the
    scanner/chunker still work while symbol-level features simply yield nothing.
    """

    factory = _PARSER_FACTORIES.get(language)
    if factory is not None:
        return factory()
    return _NullParser(language)


class _NullParser:
    """Fallback parser for unsupported languages: yields no symbols."""

    def __init__(self, language: str) -> None:
        self.language = language

    def parse(self, source: str, rel_path: str) -> ParseResult:
        return ParseResult(language=self.language)
