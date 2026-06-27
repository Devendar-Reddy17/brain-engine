"""Language-agnostic tag derivation.

Tags are normalized, cross-language labels (e.g. ``controller``, ``service``,
``repository``, ``route``, ``test``, ``api``) derived from a symbol's raw
annotations/decorators/attributes plus structural hints (``route``,
``is_test``). They power local repository queries without baking
framework-specific logic into the query layer.

Derivation happens in ONE place, after parsing (see
``symbol_extractor.extract``), so individual parsers stay tag-agnostic and only
need to populate raw ``annotations``/``route``/``is_test`` on each
:class:`~brain.core.parsing.parser.ParsedSymbol`.

New languages register a tagger via :func:`register_language_tagger`.
"""

from __future__ import annotations

from typing import Callable

from brain.core.parsing.parser import ParsedSymbol

# Re-exported single source of truth (do not redefine here).
from brain.core.versions import TAGGER_VERSION  # noqa: F401

LanguageTagger = Callable[[ParsedSymbol], list[str]]

_LANGUAGE_TAGGERS: dict[str, LanguageTagger] = {}


def register_language_tagger(language: str, tagger: LanguageTagger) -> None:
    """Register a per-language tagger. Later registrations override earlier."""

    _LANGUAGE_TAGGERS[language] = tagger


def derive_tags(symbol: ParsedSymbol, language: str) -> list[str]:
    """Return the de-duplicated, ordered tag list for ``symbol``.

    Combines language-agnostic structural tags with any language-specific tags.
    """

    tags: list[str] = []

    # Structural, language-agnostic tags.
    if symbol.route is not None or symbol.kind == "route":
        tags.append("route")
        tags.append("api")
    if symbol.is_test or symbol.kind == "test":
        tags.append("test")

    # Language-specific stereotype/annotation tags.
    lang_tagger = _LANGUAGE_TAGGERS.get(language)
    if lang_tagger is not None:
        tags.extend(lang_tagger(symbol))

    return _dedup(tags)


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


# -- tagger registration ---------------------------------------------------
# Imported here (after the registry is defined) so each language tagger plugs
# in without creating an import cycle. New languages: add a module under
# ``taggers`` exposing ``LANGUAGE`` and ``derive`` and register it below.
from brain.core.parsing.taggers import java_spring, python_web  # noqa: E402

register_language_tagger(java_spring.LANGUAGE, java_spring.derive)
register_language_tagger(python_web.LANGUAGE, python_web.derive)
