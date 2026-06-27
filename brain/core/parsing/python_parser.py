"""Python parser built on the standard-library :mod:`ast`.

Extracts module/imports, classes (with base classes and decorators),
functions/methods (with decorators, signatures, call sites), HTTP route handlers
(FastAPI/Flask/DRF-style decorators) and test functions.

Like every parser, this stays *tag-agnostic*: it only records neutral facts
(decorators in ``annotations``, base classes in ``extends``, route strings, and
a ``framework_metadata`` bag). Stereotype tags (``controller``/``service``/...)
are derived later by :mod:`brain.core.parsing.taggers.python_web`.

Being stdlib-only, it has no third-party dependency and works wherever Python
runs. Syntax errors degrade gracefully to a module-only ParseResult.
"""

from __future__ import annotations

import ast

from brain.core.parsing.parser import ParsedSymbol, ParseResult
from brain.utils.logger import get_logger

log = get_logger(__name__)

# Decorator attribute names that denote an HTTP route handler.
_HTTP_METHODS: frozenset[str] = frozenset(
    {"get", "post", "put", "delete", "patch", "options", "head", "trace"}
)

_TYPE_KINDS = {"class"}


class PythonParser:
    language = "python"

    # -- public API -------------------------------------------------------
    def parse(self, source: str, rel_path: str) -> ParseResult:
        result = ParseResult(language=self.language)
        result.package = _module_name(rel_path)

        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            log.warning("Python parse failed for %s: %s", rel_path, exc)
            return result

        for node in tree.body:
            self._visit_top_level(node, result)
        return result

    # -- top-level dispatch ----------------------------------------------
    def _visit_top_level(self, node: ast.AST, result: ParseResult) -> None:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for name in _import_names(node):
                result.imports.append(name)
            return
        if isinstance(node, ast.ClassDef):
            self._visit_class(node, result, parent=None)
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._visit_function(node, result, owner=None)
            return

    # -- class ------------------------------------------------------------
    def _visit_class(self, node: ast.ClassDef, result: ParseResult, parent: str | None) -> None:
        decorators = [_dotted(d) for d in node.decorator_list]
        bases = [b for b in (_dotted(base) for base in node.bases) if b]
        is_test = node.name.startswith("Test")

        result.symbols.append(
            ParsedSymbol(
                name=node.name,
                kind="class",
                start_line=node.lineno,
                end_line=_end_line(node),
                parent_symbol=parent,
                visibility=_visibility(node.name),
                annotations=[d for d in decorators if d],
                extends=bases,
                is_test=is_test,
            )
        )

        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._visit_function(child, result, owner=node.name, class_is_test=is_test)
            elif isinstance(child, ast.ClassDef):
                self._visit_class(child, result, parent=node.name)

    # -- function / method ------------------------------------------------
    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        result: ParseResult,
        owner: str | None,
        class_is_test: bool = False,
    ) -> None:
        decorators = [_dotted(d) for d in node.decorator_list]
        route, metadata = self._derive_route(node)
        is_test = node.name.startswith("test_") or (class_is_test and node.name.startswith("test"))

        base_kind = "method" if owner is not None else "function"
        kind = "route" if route is not None else base_kind
        if is_test:
            kind = "test"

        result.symbols.append(
            ParsedSymbol(
                name=node.name,
                kind=kind,
                start_line=node.lineno,
                end_line=_end_line(node),
                parent_symbol=owner,
                signature=_signature(node),
                visibility=_visibility(node.name),
                annotations=[d for d in decorators if d],
                calls=_collect_calls(node),
                is_test=is_test,
                route=route,
                framework_metadata=metadata,
            )
        )

    def _derive_route(self, node: ast.AST) -> tuple[str | None, dict]:
        """Return ``(route, framework_metadata)`` from HTTP route decorators."""

        for deco in getattr(node, "decorator_list", []):
            if not isinstance(deco, ast.Call):
                continue
            dotted = _dotted(deco.func)
            if not dotted:
                continue
            attr = dotted.rsplit(".", 1)[-1]
            if attr in _HTTP_METHODS:
                verb = attr.upper()
            elif attr == "route":
                methods = _route_methods(deco)
                verb = methods[0] if methods else "GET"
            else:
                continue
            path = _first_str_arg(deco)
            route = f"{verb} {path}".strip()
            return route, {"decorator": dotted, "http_method": verb}
        return None, {}


# -- module-level helpers ---------------------------------------------------
def _module_name(rel_path: str) -> str:
    norm = rel_path.replace("\\", "/")
    if norm.endswith(".py"):
        norm = norm[:-3]
    parts = [p for p in norm.split("/") if p and p != "__init__"]
    return ".".join(parts)


def _import_names(node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    module = node.module or ""
    if not node.names:
        return [module] if module else []
    out: list[str] = []
    for alias in node.names:
        if alias.name == "*":
            out.append(module)
        else:
            out.append(f"{module}.{alias.name}" if module else alias.name)
    return out


def _dotted(node: ast.AST) -> str:
    """Best-effort dotted name for a decorator/base-class expression."""

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _dotted(node.func)
    if isinstance(node, ast.Subscript):
        return _dotted(node.value)
    return ""


def _first_str_arg(call: ast.Call) -> str:
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    for kw in call.keywords:
        if kw.arg in ("path", "rule") and isinstance(kw.value, ast.Constant):
            if isinstance(kw.value.value, str):
                return kw.value.value
    return ""


def _route_methods(call: ast.Call) -> list[str]:
    for kw in call.keywords:
        if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple, ast.Set)):
            methods: list[str] = []
            for elt in kw.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    methods.append(elt.value.upper())
            return methods
    return []


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = node.args
    names: list[str] = []
    names.extend(a.arg for a in getattr(args, "posonlyargs", []))
    names.extend(a.arg for a in args.args)
    if args.vararg is not None:
        names.append(f"*{args.vararg.arg}")
    names.extend(a.arg for a in args.kwonlyargs)
    if args.kwarg is not None:
        names.append(f"**{args.kwarg.arg}")
    return f"{node.name}({', '.join(names)})"


def _collect_calls(node: ast.AST) -> list[str]:
    calls: list[str] = []
    seen: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = ""
            func = child.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name and name not in seen:
                seen.add(name)
                calls.append(name)
    return calls


def _visibility(name: str) -> str:
    return "private" if name.startswith("_") else "public"


def _end_line(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    if end is not None:
        return int(end)
    return int(getattr(node, "lineno", 1))
