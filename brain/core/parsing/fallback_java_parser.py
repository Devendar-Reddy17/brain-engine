"""Regex-based Java parser used when tree-sitter is unavailable.

Less precise than the tree-sitter parser but dependency-free. Extracts package,
imports, types, methods, Spring annotations, routes, and test methods. Line
numbers are derived from match positions.
"""

from __future__ import annotations

import re

from brain.core.parsing.parser import ParsedSymbol, ParseResult
from brain.core.parsing import spring

_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
_IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w.*]+)\s*;", re.MULTILINE)
_TYPE_RE = re.compile(
    r"(?P<mods>(?:@\w+(?:\([^)]*\))?\s*)*)"
    r"(?P<vis>public|protected|private)?\s*"
    r"(?:abstract\s+|final\s+|static\s+)*"
    r"(?P<kind>class|interface|enum)\s+"
    r"(?P<name>\w+)"
    r"(?:\s+extends\s+(?P<extends>[\w.<>,\s]+?))?"
    r"(?:\s+implements\s+(?P<implements>[\w.<>,\s]+?))?"
    r"\s*\{",
    re.MULTILINE,
)
_METHOD_RE = re.compile(
    r"(?P<anns>(?:@\w+(?:\([^)]*\))?\s*)*)"
    r"(?P<vis>public|protected|private)?\s*"
    r"(?:static\s+|final\s+|abstract\s+|synchronized\s+|default\s+)*"
    r"(?P<ret>[\w.<>\[\],\s]+?)\s+"
    r"(?P<name>\w+)\s*"
    r"\((?P<params>[^)]*)\)\s*"
    r"(?:throws\s+[\w.,\s]+)?\s*[{;]",
    re.MULTILINE,
)
_ANNOTATION_RE = re.compile(r"@(\w+)(?:\(([^)]*)\))?")


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


class FallbackJavaParser:
    language = "java"

    def parse(self, source: str, rel_path: str) -> ParseResult:
        result = ParseResult(language=self.language)

        pkg = _PACKAGE_RE.search(source)
        if pkg:
            result.package = pkg.group(1)
            result.symbols.append(
                ParsedSymbol(name=pkg.group(1), kind="package",
                             start_line=_line_of(source, pkg.start()),
                             end_line=_line_of(source, pkg.end()))
            )

        for m in _IMPORT_RE.finditer(source):
            imported = m.group(1)
            result.imports.append(imported)
            result.symbols.append(
                ParsedSymbol(name=imported, kind="import",
                             start_line=_line_of(source, m.start()),
                             end_line=_line_of(source, m.end()))
            )

        class_route = self._class_request_mapping(source)
        current_owner = None

        for m in _TYPE_RE.finditer(source):
            name = m.group("name")
            current_owner = name
            annotations = [a[0] for a in _ANNOTATION_RE.findall(m.group("mods") or "")]
            extends = self._split_types(m.group("extends"))
            implements = self._split_types(m.group("implements"))
            result.symbols.append(
                ParsedSymbol(
                    name=name,
                    kind=m.group("kind"),
                    start_line=_line_of(source, m.start("name")),
                    end_line=_line_of(source, m.end()),
                    visibility=m.group("vis") or "package",
                    annotations=annotations,
                    extends=extends,
                    implements=implements,
                )
            )

        for m in self._iter_methods(source):
            name = m["name"]
            annotations = m["annotations"]
            is_test = any(spring.is_test_annotation(a) for a in annotations)
            route = self._derive_route(annotations, m["ann_args"], class_route)
            kind = "route" if route else "method"
            result.symbols.append(
                ParsedSymbol(
                    name=name,
                    kind="test" if is_test else kind,
                    start_line=m["line"],
                    end_line=m["line"],
                    parent_symbol=current_owner,
                    signature=f"{name}({m['params']})",
                    visibility=m["vis"],
                    annotations=annotations,
                    is_test=is_test,
                    route=route,
                )
            )

        return result

    # -- helpers ----------------------------------------------------------
    def _split_types(self, raw: str | None) -> list[str]:
        if not raw:
            return []
        return [t.split("<")[0].strip() for t in raw.split(",") if t.strip()]

    def _class_request_mapping(self, source: str) -> str | None:
        # Find a @RequestMapping immediately preceding a class declaration.
        match = re.search(r'@RequestMapping\s*\(([^)]*)\)\s*(?:@\w+(?:\([^)]*\))?\s*)*\s*(?:public|final|abstract|\s)*class', source)
        if match:
            return match.group(1)
        return None

    def _iter_methods(self, source: str):
        # Common Java keywords that the method regex may falsely match.
        skip_names = {"if", "for", "while", "switch", "catch", "return", "new"}
        for m in _METHOD_RE.finditer(source):
            name = m.group("name")
            if name in skip_names:
                continue
            ret = (m.group("ret") or "").strip()
            if ret in ("return", "new", "else"):
                continue
            ann_block = m.group("anns") or ""
            anns = _ANNOTATION_RE.findall(ann_block)
            yield {
                "name": name,
                "params": m.group("params").strip(),
                "vis": m.group("vis") or "package",
                "annotations": [a[0] for a in anns],
                "ann_args": {a[0]: a[1] for a in anns},
                "line": _line_of(source, m.start("name")),
            }

    def _derive_route(self, annotations: list[str], ann_args: dict[str, str], class_route: str | None) -> str | None:
        for ann in annotations:
            method = spring.mapping_http_method(ann)
            if method is False:
                continue
            path = (ann_args.get(ann, "") or "").strip().strip('"')
            base = (class_route or "").strip().strip('"')
            full = "/".join(p for p in (base, path) if p).replace("//", "/")
            verb = method if isinstance(method, str) else "ANY"
            return f"{verb} {full}".strip()
        return None
