"""Java / Spring tagger.

Maps Spring stereotype annotations to normalized tags. Structural tags (route,
test) are handled by the shared derivation in :mod:`brain.core.parsing.tagging`;
this tagger only contributes the language/framework-specific stereotypes.
"""

from __future__ import annotations

from brain.core.parsing import spring
from brain.core.parsing.parser import ParsedSymbol

LANGUAGE = "java"

# Map normalized stereotype annotation -> tag.
_STEREOTYPE_TAGS: dict[str, str] = {
    "RestController": "controller",
    "Controller": "controller",
    "Service": "service",
    "Repository": "repository",
    "Component": "component",
    "Configuration": "config",
}


def derive(symbol: ParsedSymbol) -> list[str]:
    tags: list[str] = []
    for ann in symbol.annotations:
        norm = spring.normalize_annotation(ann)
        tag = _STEREOTYPE_TAGS.get(norm)
        if tag is not None:
            tags.append(tag)
    # Controllers expose an HTTP API surface.
    if "controller" in tags:
        tags.append("api")
    return tags
