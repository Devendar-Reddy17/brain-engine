"""Tags for JavaScript/TypeScript frontend and API frameworks."""

from __future__ import annotations

from brain.core.parsing.parser import ParsedSymbol

LANGUAGES = ("typescript", "javascript")


def derive(symbol: ParsedSymbol) -> list[str]:
    tags: list[str] = []
    annotations = {a.lower() for a in symbol.annotations}
    name = symbol.name.lower()
    path = symbol.file_path.replace("\\", "/").lower()

    if "component" in annotations or "component" in path or _is_react_component(symbol):
        tags.extend(["component", "ui"])
    if "injectable" in annotations or "/service" in path or name.endswith("service"):
        tags.append("service")
    if "/store" in path or name.endswith("store"):
        tags.append("store")
    if "/hook" in path or name.startswith("use"):
        tags.append("hook")
    if "/page" in path or "/view" in path:
        tags.append("page")
    if "/api" in path or "/route" in path or symbol.kind == "route":
        tags.append("api")
    if "controller" in annotations or name.endswith("controller"):
        tags.append("controller")

    return tags


def _is_react_component(symbol: ParsedSymbol) -> bool:
    if symbol.kind not in {"function", "class"}:
        return False
    return bool(symbol.name and symbol.name[0].isupper())
