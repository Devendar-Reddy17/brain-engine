"""Tree-sitter based Java parser.

Extracts package, imports, classes/interfaces/enums, methods/constructors,
fields/constants, Spring annotations, route handlers, test methods, and method
invocations (for the dependency graph).

The tree-sitter Python API changed across versions; :func:`_build_parser`
tries the known construction strategies and raises if none work, allowing the
factory in ``parser.py`` to fall back to the regex parser.
"""

from __future__ import annotations

from brain.core.parsing.parser import ParsedSymbol, ParseResult
from brain.core.parsing import spring
from brain.utils.logger import get_logger

log = get_logger(__name__)


def _build_parser():
    """Construct a tree-sitter Parser bound to the Java grammar.

    Supports both the 0.21 and 0.22+ Python API shapes.
    """

    import tree_sitter_java as tsjava
    from tree_sitter import Language, Parser

    lang_capsule = tsjava.language()

    language = None
    errors: list[str] = []
    # Newer API: Language(capsule)
    try:
        language = Language(lang_capsule)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Language(capsule): {exc}")
        # Older API: Language(capsule, "java")
        try:
            language = Language(lang_capsule, "java")  # type: ignore[call-arg]
        except Exception as exc2:  # noqa: BLE001
            errors.append(f"Language(capsule, name): {exc2}")
            raise RuntimeError("; ".join(errors))

    # Parser construction: Parser(language) (new) or Parser()+set_language (old)
    try:
        return Parser(language)  # type: ignore[call-arg]
    except Exception:
        parser = Parser()
        try:
            parser.language = language  # type: ignore[attr-defined]
        except Exception:
            parser.set_language(language)  # type: ignore[attr-defined]
        return parser


class JavaParser:
    language = "java"

    def __init__(self) -> None:
        self._parser = _build_parser()

    # -- public API -------------------------------------------------------
    def parse(self, source: str, rel_path: str) -> ParseResult:
        data = source.encode("utf-8")
        tree = self._parser.parse(data)
        root = tree.root_node

        result = ParseResult(language=self.language)
        self._walk_top_level(root, data, result, parent=None)
        return result

    # -- helpers ----------------------------------------------------------
    def _text(self, node, data: bytes) -> str:
        return data[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _line(self, node) -> int:
        return node.start_point[0] + 1

    def _end_line(self, node) -> int:
        return node.end_point[0] + 1

    def _child_by_field(self, node, field: str):
        return node.child_by_field_name(field)

    def _collect_annotations(self, node, data: bytes) -> list[str]:
        """Collect annotation names from a node's `modifiers` child."""

        annotations: list[str] = []
        modifiers = None
        for child in node.children:
            if child.type == "modifiers":
                modifiers = child
                break
        if modifiers is None:
            return annotations
        for child in modifiers.children:
            if child.type in ("annotation", "marker_annotation"):
                name_node = self._child_by_field(child, "name")
                if name_node is not None:
                    annotations.append(self._text(name_node, data))
        return annotations

    def _annotation_args(self, node, data: bytes, annotation_name: str) -> str | None:
        """Return the raw argument text for a given annotation on this node."""

        for child in node.children:
            if child.type != "modifiers":
                continue
            for ann in child.children:
                if ann.type not in ("annotation", "marker_annotation"):
                    continue
                name_node = self._child_by_field(ann, "name")
                if name_node is None:
                    continue
                if spring.normalize_annotation(self._text(name_node, data)) == annotation_name:
                    args = self._child_by_field(ann, "arguments")
                    return self._text(args, data) if args is not None else ""
        return None

    def _visibility(self, node, data: bytes) -> str:
        for child in node.children:
            if child.type == "modifiers":
                text = self._text(child, data)
                for vis in ("public", "protected", "private"):
                    if vis in text.split():
                        return vis
                return "package"
        return "package"

    def _walk_top_level(self, root, data: bytes, result: ParseResult, parent: str | None) -> None:
        for child in root.children:
            self._visit(child, data, result, parent)

    def _visit(self, node, data: bytes, result: ParseResult, parent: str | None) -> None:
        ntype = node.type
        if ntype == "package_declaration":
            ident = self._first_identifier_text(node, data)
            if ident:
                result.package = ident
                result.symbols.append(
                    ParsedSymbol(
                        name=ident,
                        kind="package",
                        start_line=self._line(node),
                        end_line=self._end_line(node),
                    )
                )
            return

        if ntype == "import_declaration":
            text = self._text(node, data).strip().rstrip(";")
            imported = text.replace("import", "", 1).replace("static", "").strip()
            if imported:
                result.imports.append(imported)
                result.symbols.append(
                    ParsedSymbol(
                        name=imported,
                        kind="import",
                        start_line=self._line(node),
                        end_line=self._end_line(node),
                    )
                )
            return

        if ntype in ("class_declaration", "interface_declaration", "enum_declaration"):
            self._visit_type(node, data, result, parent, ntype)
            return

    def _visit_type(self, node, data: bytes, result: ParseResult, parent: str | None, ntype: str) -> None:
        name_node = self._child_by_field(node, "name")
        name = self._text(name_node, data) if name_node else "<anonymous>"
        annotations = self._collect_annotations(node, data)
        kind = {
            "class_declaration": "class",
            "interface_declaration": "interface",
            "enum_declaration": "enum",
        }[ntype]

        extends: list[str] = []
        implements: list[str] = []
        superclass = self._child_by_field(node, "superclass")
        if superclass is not None:
            extends.append(self._strip_type(self._text(superclass, data)))
        interfaces = self._child_by_field(node, "interfaces")
        if interfaces is not None:
            implements.extend(self._type_names(interfaces, data))

        # Base path from @RequestMapping at class level (for route composition)
        class_route = self._annotation_args(node, data, "RequestMapping")

        symbol = ParsedSymbol(
            name=name,
            kind=kind,
            start_line=self._line(node),
            end_line=self._end_line(node),
            parent_symbol=parent,
            visibility=self._visibility(node, data),
            annotations=annotations,
            extends=extends,
            implements=implements,
        )
        result.symbols.append(symbol)

        body = self._child_by_field(node, "body")
        if body is not None:
            for member in body.children:
                self._visit_member(member, data, result, name, class_route)

    def _visit_member(self, node, data: bytes, result: ParseResult, owner: str, class_route: str | None) -> None:
        if node.type in ("method_declaration", "constructor_declaration"):
            self._visit_method(node, data, result, owner, class_route)
        elif node.type == "field_declaration":
            self._visit_field(node, data, result, owner)
        elif node.type in ("class_declaration", "interface_declaration", "enum_declaration"):
            self._visit_type(node, data, result, owner, node.type)

    def _visit_method(self, node, data: bytes, result: ParseResult, owner: str, class_route: str | None) -> None:
        name_node = self._child_by_field(node, "name")
        name = self._text(name_node, data) if name_node else "<init>"
        annotations = self._collect_annotations(node, data)
        params = self._child_by_field(node, "parameters")
        signature = f"{name}{self._text(params, data) if params else '()'}"
        kind = "constructor" if node.type == "constructor_declaration" else "method"

        is_test = any(spring.is_test_annotation(a) for a in annotations)
        route = self._derive_route(node, data, annotations, class_route)
        if route is not None:
            kind = "route"

        calls = self._collect_calls(node, data)

        result.symbols.append(
            ParsedSymbol(
                name=name,
                kind="test" if is_test else kind,
                start_line=self._line(node),
                end_line=self._end_line(node),
                parent_symbol=owner,
                signature=signature,
                visibility=self._visibility(node, data),
                annotations=annotations,
                calls=calls,
                is_test=is_test,
                route=route,
            )
        )

    def _visit_field(self, node, data: bytes, result: ParseResult, owner: str) -> None:
        annotations = self._collect_annotations(node, data)
        declarator = None
        for child in node.children:
            if child.type == "variable_declarator":
                declarator = child
                break
        if declarator is None:
            return
        name_node = self._child_by_field(declarator, "name")
        name = self._text(name_node, data) if name_node else "<field>"
        text = self._text(node, data)
        is_const = "static" in text and "final" in text
        result.symbols.append(
            ParsedSymbol(
                name=name,
                kind="constant" if is_const else "field",
                start_line=self._line(node),
                end_line=self._end_line(node),
                parent_symbol=owner,
                visibility=self._visibility(node, data),
                annotations=annotations,
            )
        )

    def _collect_calls(self, node, data: bytes) -> list[str]:
        calls: list[str] = []

        def walk(n) -> None:
            if n.type == "method_invocation":
                name_node = n.child_by_field_name("name")
                if name_node is not None:
                    calls.append(self._text(name_node, data))
            for c in n.children:
                walk(c)

        walk(node)
        # de-dup, preserve order
        seen: set[str] = set()
        out: list[str] = []
        for c in calls:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _derive_route(self, node, data: bytes, annotations: list[str], class_route: str | None) -> str | None:
        for ann in annotations:
            method = spring.mapping_http_method(ann)
            if method is False:
                continue
            path = self._annotation_args(node, data, spring.normalize_annotation(ann)) or ""
            path = path.strip("()").strip().strip('"')
            base = (class_route or "").strip("()").strip().strip('"')
            full = "/".join(p for p in (base, path) if p).replace("//", "/")
            verb = method if isinstance(method, str) else "ANY"
            return f"{verb} {full}".strip()
        return None

    # -- node text utilities ---------------------------------------------
    def _first_identifier_text(self, node, data: bytes) -> str | None:
        for child in node.children:
            if child.type in ("scoped_identifier", "identifier"):
                return self._text(child, data)
        return None

    def _strip_type(self, text: str) -> str:
        text = text.replace("extends", "").strip()
        return text.split("<")[0].strip()

    def _type_names(self, node, data: bytes) -> list[str]:
        names: list[str] = []

        def walk(n) -> None:
            if n.type in ("type_identifier", "scoped_type_identifier"):
                names.append(self._text(n, data).split("<")[0].strip())
            for c in n.children:
                walk(c)

        walk(node)
        return names
