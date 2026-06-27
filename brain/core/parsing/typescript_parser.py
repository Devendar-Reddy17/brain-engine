"""Lightweight JavaScript/TypeScript parser.

This is a dependency-free parser intended to give React, Angular, Nest, and
Express projects useful symbols/chunks until a tree-sitter based parser is
added. It extracts imports, decorators, classes, functions, exported const
components/handlers, basic call sites, and common HTTP route declarations.
"""

from __future__ import annotations

import re

from brain.core.parsing.parser import ParsedSymbol, ParseResult

_IMPORT_RE = re.compile(r"^\s*import\s+(?:.+?\s+from\s+)?[\"']([^\"']+)[\"']", re.MULTILINE)
_CLASS_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)", re.MULTILINE)
_FUNCTION_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)", re.MULTILINE)
_CONST_FUNC_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>",
    re.MULTILINE,
)
_METHOD_RE = re.compile(r"^\s*(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{", re.MULTILINE)
_ANGULAR_DECORATOR_RE = re.compile(r"^\s*@([A-Za-z_$][\w$]*)\s*\(", re.MULTILINE)
_NEST_CONTROLLER_RE = re.compile(r"@Controller\s*\(\s*([\"'`])([^\"'`]*)\1\s*\)")
_NEST_METHOD_RE = re.compile(r"@(Get|Post|Put|Delete|Patch|Head|Options)\s*\(\s*(?:([\"'`])([^\"'`]*)\2)?\s*\)")
_EXPRESS_ROUTE_RE = re.compile(
    r"\b(?:app|router)\.(get|post|put|delete|patch|head|options)\s*\(\s*([\"'`])([^\"'`]+)\2",
    re.IGNORECASE,
)
_CALL_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")


class TypeScriptParser:
    def __init__(self, language: str = "typescript") -> None:
        self.language = language

    def parse(self, source: str, rel_path: str) -> ParseResult:
        result = ParseResult(language=self.language, package=_module_name(rel_path))
        result.imports.extend(_IMPORT_RE.findall(source))

        lines = source.splitlines()
        decorators_by_line = _decorators_by_line(source, lines)
        class_routes = _class_route_bases(source, lines)

        for match in _CLASS_RE.finditer(source):
            line = _line_for_offset(source, match.start())
            name = match.group(1)
            annotations = decorators_by_line.get(line, [])
            result.symbols.append(
                ParsedSymbol(
                    name=name,
                    kind="class",
                    start_line=line,
                    end_line=_block_end(lines, line),
                    annotations=annotations,
                    visibility="public",
                )
            )

        for regex in (_FUNCTION_RE, _CONST_FUNC_RE):
            for match in regex.finditer(source):
                line = _line_for_offset(source, match.start())
                name = match.group(1)
                route = _method_route(source, lines, line, class_routes)
                result.symbols.append(
                    ParsedSymbol(
                        name=name,
                        kind="route" if route else "function",
                        start_line=line,
                        end_line=_block_end(lines, line),
                        signature=f"{name}()",
                        annotations=decorators_by_line.get(line, []),
                        calls=_calls_near(lines, line),
                        route=route,
                        framework_metadata={"framework": "typescript"} if route else {},
                    )
                )

        class_ranges = _class_ranges(source, lines)
        for match in _METHOD_RE.finditer(source):
            line = _line_for_offset(source, match.start())
            name = match.group(1)
            if name in {"if", "for", "while", "switch", "catch", "function"}:
                continue
            owner = _owner_for_line(class_ranges, line)
            if owner is None:
                continue
            route = _method_route(source, lines, line, class_routes)
            result.symbols.append(
                ParsedSymbol(
                    name=name,
                    kind="route" if route else "method",
                    start_line=line,
                    end_line=_block_end(lines, line),
                    parent_symbol=owner,
                    signature=f"{name}()",
                    annotations=decorators_by_line.get(line, []),
                    calls=_calls_near(lines, line),
                    route=route,
                    framework_metadata={"framework": "typescript"} if route else {},
                )
            )

        for match in _EXPRESS_ROUTE_RE.finditer(source):
            line = _line_for_offset(source, match.start())
            method = match.group(1).upper()
            path = match.group(3)
            name = _route_handler_name(lines[line - 1], method, path)
            result.symbols.append(
                ParsedSymbol(
                    name=name,
                    kind="route",
                    start_line=line,
                    end_line=_block_end(lines, line),
                    annotations=[f"router.{method.lower()}"],
                    calls=_calls_near(lines, line),
                    route=f"{method} {path}",
                    framework_metadata={"framework": "express"},
                )
            )

        return result


class JavaScriptParser(TypeScriptParser):
    def __init__(self) -> None:
        super().__init__("javascript")


def _module_name(rel_path: str) -> str:
    norm = rel_path.replace("\\", "/")
    for ext in (".tsx", ".ts", ".jsx", ".js"):
        if norm.endswith(ext):
            norm = norm[: -len(ext)]
            break
    return ".".join(p for p in norm.split("/") if p)


def _line_for_offset(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _decorators_by_line(source: str, lines: list[str]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for match in _ANGULAR_DECORATOR_RE.finditer(source):
        dec_line = _line_for_offset(source, match.start())
        target = _next_code_line(lines, dec_line + 1)
        if target:
            out.setdefault(target, []).append(match.group(1))
    return out


def _class_route_bases(source: str, lines: list[str]) -> dict[tuple[int, int], str]:
    bases: dict[tuple[int, int], str] = {}
    for match in _NEST_CONTROLLER_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        class_line = _next_matching_line(lines, line, re.compile(r"\bclass\b"))
        if class_line:
            bases[(class_line, _block_end(lines, class_line))] = "/" + match.group(2).strip("/")
    return bases


def _class_ranges(source: str, lines: list[str]) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    for match in _CLASS_RE.finditer(source):
        line = _line_for_offset(source, match.start())
        ranges.append((line, _block_end(lines, line), match.group(1)))
    return ranges


def _owner_for_line(class_ranges: list[tuple[int, int, str]], line: int) -> str | None:
    for start, end, name in class_ranges:
        if start < line <= end:
            return name
    return None


def _method_route(source: str, lines: list[str], line: int, class_routes: dict[tuple[int, int], str]) -> str | None:
    prefix = "\n".join(lines[max(0, line - 4):line])
    match = _NEST_METHOD_RE.search(prefix)
    if not match:
        return None
    method = match.group(1).upper()
    path = match.group(3) or ""
    base = ""
    for (start, end), route_base in class_routes.items():
        if start <= line <= end:
            base = route_base
            break
    full = "/".join(p.strip("/") for p in (base, path) if p.strip("/"))
    return f"{method} /{full}".rstrip("/")


def _next_code_line(lines: list[str], start_line: int) -> int | None:
    for i in range(start_line - 1, len(lines)):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith("@"):
            return i + 1
    return None


def _next_matching_line(lines: list[str], start_line: int, pattern: re.Pattern) -> int | None:
    for i in range(start_line - 1, len(lines)):
        if pattern.search(lines[i]):
            return i + 1
    return None


def _block_end(lines: list[str], start_line: int) -> int:
    depth = 0
    started = False
    for i in range(start_line - 1, len(lines)):
        line = _strip_strings(lines[i])
        depth += line.count("{")
        if "{" in line:
            started = True
        depth -= line.count("}")
        if started and depth <= 0:
            return i + 1
    return min(len(lines), start_line + 80)


def _strip_strings(line: str) -> str:
    return re.sub(r"([\"'`]).*?\1", "", line)


def _calls_near(lines: list[str], start_line: int) -> list[str]:
    end = min(len(lines), start_line + 80)
    text = "\n".join(lines[start_line - 1:end])
    seen: set[str] = set()
    calls: list[str] = []
    for name in _CALL_RE.findall(text):
        if name in {"if", "for", "while", "switch", "return", "function"}:
            continue
        if name not in seen:
            seen.add(name)
            calls.append(name)
    return calls


def _route_handler_name(line: str, method: str, path: str) -> str:
    match = re.search(r",\s*([A-Za-z_$][\w$]*)\s*[),]", line)
    if match:
        return match.group(1)
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_") or "root"
    return f"{method.lower()}_{suffix}"
