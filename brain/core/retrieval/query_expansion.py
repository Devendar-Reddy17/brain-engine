"""Generic prompt expansion helpers for repository retrieval.

These helpers are intentionally repo/domain agnostic. They derive common code
search aliases from the user's words, especially acronyms that developers often
use in identifiers (``role based access control`` -> ``rbac``).
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*|\d+[A-Za-z]*")

_GENERIC_WORDS = {
    "a",
    "an",
    "and",
    "any",
    "are",
    "can",
    "code",
    "codebase",
    "does",
    "explain",
    "find",
    "flow",
    "for",
    "from",
    "have",
    "how",
    "in",
    "is",
    "of",
    "or",
    "please",
    "repo",
    "repository",
    "show",
    "system",
    "the",
    "this",
    "to",
    "use",
    "uses",
    "what",
    "where",
    "with",
}

_QUANTITY_EQUIVALENTS = {
    "2": ("two", "multi"),
    "two": ("2", "multi"),
    "multi": ("two", "2"),
}


def expand_prompt_aliases(prompt: str) -> list[str]:
    """Return generic search aliases derived from *prompt*.

    The expansion is deliberately conservative:
    - short alphanumeric tokens such as ``2fa`` are preserved;
    - 3-5 word phrases become acronym candidates;
    - quantity-like words get equivalent variants so ``two factor auth`` can
      also probe ``mfa``/``2fa``-style code without a domain-specific rule.
    """

    words = [w.lower() for w in _WORD_RE.findall(prompt)]
    aliases: list[str] = []

    for word in words:
        if 2 <= len(word) <= 8 and any(ch.isalpha() for ch in word) and any(ch.isdigit() for ch in word):
            aliases.append(word)

    for size in range(3, 6):
        for i in range(0, max(0, len(words) - size + 1)):
            phrase = words[i:i + size]
            if not _has_signal_word(phrase):
                continue
            for variant in _phrase_variants(phrase):
                acronym = _acronym(variant)
                if _is_useful_alias(acronym):
                    aliases.append(acronym)

    return _dedup(aliases)


def _phrase_variants(words: list[str]) -> list[list[str]]:
    variants = [words]
    for i, word in enumerate(words):
        replacements = _QUANTITY_EQUIVALENTS.get(word)
        if not replacements:
            continue
        for replacement in replacements:
            variant = list(words)
            variant[i] = replacement
            variants.append(variant)
    return variants


def _acronym(words: list[str]) -> str:
    letters: list[str] = []
    for word in words:
        if word.isdigit():
            letters.append(word)
        else:
            letters.append(word[0])
    return "".join(letters)


def _has_signal_word(words: list[str]) -> bool:
    return sum(1 for word in words if word not in _GENERIC_WORDS) >= 2


def _is_useful_alias(alias: str) -> bool:
    if len(alias) < 3 or len(alias) > 8:
        return False
    if alias.isdigit():
        return False
    return alias not in _GENERIC_WORDS


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if key and key.lower() not in seen:
            seen.add(key.lower())
            out.append(key)
    return out
