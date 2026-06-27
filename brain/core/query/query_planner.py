"""QueryPlanner: the single routing point for repository questions.

Given a natural-language question, the planner decides whether it can be
answered deterministically from the local Brain index (``local``) or whether it
requires AI reasoning (``ai_required``). It NEVER calls an AI provider itself;
on ``ai_required`` the daemon hands back a context package and the client's
existing AI pipeline takes over.

Design goals:

* **Conservative** — when unsure, return ``ai_required``. Reasoning/explanation
  questions are never answered from the index.
* **Deterministic-first** — count/list/lookup questions are answered locally.
* **Stale-aware** — deterministic queries that depend on derived
  ``tags_json``/``annotations_json`` still return a ``local`` result while the
  index is stale, but attach a ``stale_warning`` telling the user to run
  ``brain index``. They are NOT guessed with AI.
* **Extensible** — new local query types register a :class:`LocalHandler`
  without touching ``/ask`` or this class. Future planners (Symbol/Graph/
  Dependency/Architecture/GitHistory/TeamKnowledge) plug into the same registry.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from brain.core.db.repositories.dependency_repository import DependencyRepository
from brain.core.db.repositories.symbol_repository import SymbolRepository

# Questions containing these cues require reasoning/summarization/generation and
# must always go to AI, even if they mention a stereotype like "controller".
_REASONING_CUES = (
    "explain",
    "describe",
    "architecture",
    "why",
    "refactor",
    "suggest",
    "compare",
    "generate",
    "implement",
    "fix",
    "should i",
    "walk me through",
    "overview",
    "how does",
    "how do",
    "design",
    "trade-off",
    "tradeoff",
    "pros and cons",
)

# An enumeration/lookup signal must be present for a local handler to engage.
_ENUMERATION_CUES = (
    "how many",
    "count",
    "list",
    "show",
    "find",
    "which",
    "all ",
    "number of",
    "what are",
    "get all",
    "display",
    "where",
    "group",
)

_STALE_WARNING = (
    "Index is out of date — results may be incomplete. Run `brain index` for "
    "accurate results."
)

_IDENTIFIER_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]+)\b")
_QUOTED_RE = re.compile(r"[\"'`]([^\"'`]+)[\"'`]")
_PATH_RE = re.compile(r"/[A-Za-z0-9_{}/-]+")

# Generic stopwords for fallback name extraction — terms too common to be
# useful as a symbol search term.
_QUERY_STOPWORDS = frozenset({
    "where", "what", "how", "why", "is", "are", "the", "a", "an",
    "present", "located", "defined", "found", "show", "find", "list",
    "get", "post", "put", "delete", "api", "route", "endpoint",
})


# -- result types ----------------------------------------------------------
@dataclass
class LocalQueryItem:
    name: str
    kind: str = ""
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    parent_symbol: str | None = None
    annotations: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class LocalQueryGroup:
    """A group of child symbols sharing the same owner/parent."""

    owner: str
    owner_kind: str = ""
    owner_file: str = ""
    items: list[LocalQueryItem] = field(default_factory=list)


@dataclass
class LocalQueryResult:
    query_type: str
    title: str
    count: int
    items: list[LocalQueryItem] = field(default_factory=list)
    groups: list[LocalQueryGroup] = field(default_factory=list)
    stale_warning: str | None = None


@dataclass
class PlanResult:
    execution_path: str  # "local" | "ai_required"
    local_result: LocalQueryResult | None = None


@dataclass
class QueryContext:
    symbols: SymbolRepository
    deps: DependencyRepository
    is_stale: bool = False


# matcher: (question_lower) -> bool ; runner: (ctx, question) -> LocalQueryResult
Matcher = Callable[[str], bool]
Runner = Callable[["QueryContext", str], LocalQueryResult]


@dataclass
class LocalHandler:
    name: str
    matcher: Matcher
    runner: Runner
    # True when the handler relies on derived tags_json/annotations_json, so a
    # stale index means results may be incomplete.
    tag_dependent: bool = False
    # True when the handler enumerates a whole category (e.g. "all routes",
    # "all controllers"). Such handlers must NOT answer a question that names a
    # specific entity (a concrete route path, a quoted term); those defer to the
    # retrieval/AI pipeline, which resolves specifics dynamically and language-
    # agnostically. Specific lookup handlers (where_is/find/which_package/
    # imports) leave this False.
    broad: bool = False


class QueryPlanner:
    def __init__(self, ctx: QueryContext, handlers: list[LocalHandler] | None = None) -> None:
        self.ctx = ctx
        self.handlers = handlers if handlers is not None else default_handlers()

    def plan(self, question: str) -> PlanResult:
        q = question.lower().strip()

        # 1. Reasoning questions always go to AI (conservative).
        if any(cue in q for cue in _REASONING_CUES):
            return PlanResult(execution_path="ai_required")

        # 2. A deterministic local query requires an enumeration/lookup signal.
        if not any(cue in q for cue in _ENUMERATION_CUES):
            return PlanResult(execution_path="ai_required")

        # When the question names a specific entity (a concrete route path or a
        # quoted term), a broad category-dump handler must not hijack it — e.g.
        # "where is GET /api/verifications/{id}" should resolve that one route,
        # not list every endpoint. Such specific questions defer to the
        # retrieval/AI pipeline, which resolves them dynamically regardless of
        # language, framework, or layer (routes, services, UI, etc.).
        names_specific = _targets_specific_entity(question)

        # 3. First matching handler wins.
        for handler in self.handlers:
            if handler.matcher(q):
                if handler.broad and names_specific:
                    continue
                result = handler.runner(self.ctx, question)
                if handler.tag_dependent and self.ctx.is_stale:
                    result.stale_warning = _STALE_WARNING
                return PlanResult(execution_path="local", local_result=result)

        # 4. No handler matched — be conservative.
        return PlanResult(execution_path="ai_required")


# -- helpers ---------------------------------------------------------------
def _targets_specific_entity(question: str) -> bool:
    """True when the question names a concrete entity rather than a category.

    A specific entity is signalled by a URL/route path (``/api/...``) or an
    explicitly quoted term. These are requests about *one* thing, so broad
    "list all X" handlers should step aside and let the retrieval/AI pipeline
    resolve the target dynamically. This is intentionally generic — it makes no
    assumption about layer (route, service, component) or language/framework.
    """

    if _QUOTED_RE.search(question):
        return True
    if _PATH_RE.search(question):
        return True
    return False


def _json_list(value) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except (ValueError, TypeError):
        return []


def _row_get(row, key, default=None):
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


def _symbol_item(row) -> LocalQueryItem:
    return LocalQueryItem(
        name=_row_get(row, "name", "") or "",
        kind=_row_get(row, "kind", "") or "",
        file_path=_row_get(row, "file_path", "") or "",
        start_line=_row_get(row, "start_line", 0) or 0,
        end_line=_row_get(row, "end_line", 0) or 0,
        parent_symbol=_row_get(row, "parent_symbol"),
        annotations=_json_list(_row_get(row, "annotations_json")),
        tags=_json_list(_row_get(row, "tags_json")),
    )


def _extract_name(question: str) -> str | None:
    # 1. Quoted terms have highest priority — user explicitly named something.
    quoted = _QUOTED_RE.findall(question)
    if quoted:
        return quoted[-1].strip()
    # 2. Path-like patterns (e.g. /api/verifications/{id}, com/pkg/Class.java).
    paths = _PATH_RE.findall(question)
    if paths:
        return paths[-1].strip()
    # 3. CamelCase identifiers.
    idents = _IDENTIFIER_RE.findall(question)
    if idents:
        return idents[-1]
    # 4. Fallback: longest non-stopword term.
    words = [w for w in re.findall(r"[A-Za-z0-9_]+", question) if w.lower() not in _QUERY_STOPWORDS and len(w) > 2]
    return words[-1] if words else None


def _extract_path(question: str) -> str | None:
    match = re.search(r"[\w./-]+\.[A-Za-z]{1,6}\b", question)
    return match.group(0) if match else None


# -- tag-based handlers (stereotypes) --------------------------------------
def _tag_handler(tag: str, label_plural: str) -> Runner:
    def run(ctx: QueryContext, question: str) -> LocalQueryResult:
        rows = ctx.symbols.list_by_tag(tag)
        items = [_symbol_item(r) for r in rows]
        return LocalQueryResult(
            query_type=f"tag:{tag}",
            title=label_plural,
            count=len(items),
            items=items,
        )

    return run


# -- structural handlers (kind / dependency based) -------------------------
def _routes_runner(ctx: QueryContext, question: str) -> LocalQueryResult:
    rows = ctx.deps.list_by_edge_type("routes_to")
    items = [
        LocalQueryItem(
            name=_row_get(r, "target_symbol_name", "") or "",
            kind="route",
            file_path=_row_get(r, "source_file", "") or "",
            start_line=_row_get(r, "source_start_line", 0) or 0,
            end_line=_row_get(r, "source_end_line", 0) or 0,
            parent_symbol=_row_get(r, "source_name"),
        )
        for r in rows
    ]
    return LocalQueryResult(
        query_type="routes",
        title="REST Endpoints",
        count=len(items),
        items=items,
    )


# Tags that mark a symbol as a potential owner/grouping parent for routes.
_OWNER_TAGS = ("controller", "router", "handler", "module", "class", "blueprint", "view")

# Phrases that signal a grouped/hierarchical display request.
_GROUPING_CUES = ("grouped by", "for each", "under each", "per ")
_CHILD_SYMBOL_CUES = ("route", "endpoint", "handler")


def _is_grouped_symbols_query(q: str) -> bool:
    """Detect route/endpoint/handler queries that ask for grouped output."""

    has_grouping = any(cue in q for cue in _GROUPING_CUES) or (
        "group" in q and " by " in q
    )
    has_child = any(cue in q for cue in _CHILD_SYMBOL_CUES)
    return has_grouping and has_child


def _grouped_routes_runner(ctx: QueryContext, question: str) -> LocalQueryResult:
    """Group route/endpoint symbols by their owning parent symbol.

    Owner resolution order:
    1. ``parent_symbol`` on the route symbol → look up in all symbols; if that
       parent has its own ``parent_symbol`` (method → class), use the
       grandparent as the owner.
    2. Enclosing symbol in the same file (start_line ≤ route.start_line ≤
       end_line), preferring symbols tagged with owner tags.
    3. File/module path fallback.
    """

    # -- collect route items from tags, kind, and structural edges ----------
    route_items: list[LocalQueryItem] = []
    seen: set[tuple[str, str, int]] = set()

    def _add_route(item: LocalQueryItem) -> None:
        key = (item.name, item.file_path, item.start_line)
        if key not in seen:
            seen.add(key)
            route_items.append(item)

    for tag in ("route", "endpoint"):
        for row in ctx.symbols.list_by_tag(tag):
            _add_route(_symbol_item(row))
    for row in ctx.symbols.list_by_kind("route"):
        _add_route(_symbol_item(row))

    for r in ctx.deps.list_by_edge_type("routes_to"):
        _add_route(
            LocalQueryItem(
                name=_row_get(r, "target_symbol_name", "") or "",
                kind="route",
                file_path=_row_get(r, "source_file", "") or "",
                start_line=_row_get(r, "source_start_line", 0) or 0,
                end_line=_row_get(r, "source_end_line", 0) or 0,
                parent_symbol=_row_get(r, "source_name"),
            )
        )

    # -- build owner-inference lookups from all symbols ---------------------
    name_to_sym: dict[str, dict] = {}
    file_to_syms: dict[str, list[dict]] = {}
    for row in ctx.symbols.list_all():
        sym = {
            "name": _row_get(row, "name", "") or "",
            "kind": _row_get(row, "kind", "") or "",
            "file_path": _row_get(row, "file_path", "") or "",
            "start_line": _row_get(row, "start_line", 0) or 0,
            "end_line": _row_get(row, "end_line", 0) or 0,
            "parent_symbol": _row_get(row, "parent_symbol"),
            "tags": _json_list(_row_get(row, "tags_json")),
        }
        name_to_sym[sym["name"]] = sym
        file_to_syms.setdefault(sym["file_path"], []).append(sym)

    # -- group routes by owner ----------------------------------------------
    groups: dict[str, LocalQueryGroup] = {}

    for route in route_items:
        owner_name: str | None = None
        owner_kind = ""
        owner_file = route.file_path

        # 1. parent_symbol → resolve through symbol table
        if route.parent_symbol:
            parent = name_to_sym.get(route.parent_symbol)
            if parent:
                if parent.get("parent_symbol"):
                    gp_name = parent["parent_symbol"]
                    gp = name_to_sym.get(gp_name)
                    if gp:
                        owner_name = gp["name"]
                        owner_kind = gp.get("kind", "")
                        owner_file = gp.get("file_path", route.file_path)
                    else:
                        owner_name = gp_name
                else:
                    owner_name = parent["name"]
                    owner_kind = parent.get("kind", "")
                    owner_file = parent.get("file_path", route.file_path)
            else:
                owner_name = route.parent_symbol

        # 2. enclosing symbol in same file
        if not owner_name and route.file_path and route.start_line:
            candidates = file_to_syms.get(route.file_path, [])
            enclosing = [
                s
                for s in candidates
                if s["start_line"] <= route.start_line <= s["end_line"]
                and s["name"] != route.name
                and s["start_line"] != route.start_line
            ]
            if enclosing:
                enclosing.sort(
                    key=lambda s: (
                        -int(any(t in _OWNER_TAGS for t in s["tags"])),
                        s["end_line"] - s["start_line"],
                    )
                )
                best = enclosing[0]
                owner_name = best["name"]
                owner_kind = best["kind"]
                owner_file = best["file_path"]

        # 3. file/module fallback
        if not owner_name:
            owner_name = route.file_path or "(unknown)"

        if owner_name not in groups:
            groups[owner_name] = LocalQueryGroup(
                owner=owner_name,
                owner_kind=owner_kind,
                owner_file=owner_file,
            )
        groups[owner_name].items.append(route)

    group_list = sorted(groups.values(), key=lambda g: g.owner)
    return LocalQueryResult(
        query_type="grouped_routes",
        title="Routes Grouped by Owner",
        count=len(route_items),
        items=route_items,
        groups=group_list,
    )


def _kind_runner(kind: str, title: str) -> Runner:
    def run(ctx: QueryContext, question: str) -> LocalQueryResult:
        rows = ctx.symbols.list_by_kind(kind)
        items = [_symbol_item(r) for r in rows]
        return LocalQueryResult(query_type=f"kind:{kind}", title=title, count=len(items), items=items)

    return run


def _edge_runner(edge_type: str, title: str) -> Runner:
    def run(ctx: QueryContext, question: str) -> LocalQueryResult:
        rows = ctx.deps.list_by_edge_type(edge_type)
        items = [
            LocalQueryItem(
                name=_row_get(r, "source_name", "") or "",
                kind=_row_get(r, "source_kind", "") or "",
                file_path=_row_get(r, "source_file", "") or "",
                start_line=_row_get(r, "source_start_line", 0) or 0,
                end_line=_row_get(r, "source_end_line", 0) or 0,
                parent_symbol=_row_get(r, "target_symbol_name"),
            )
            for r in rows
        ]
        return LocalQueryResult(query_type=f"edge:{edge_type}", title=title, count=len(items), items=items)

    return run


def _imports_runner(ctx: QueryContext, question: str) -> LocalQueryResult:
    path = _extract_path(question) or _extract_name(question) or ""
    rows = ctx.deps.imports_for_file(path) if path else []
    items = [
        LocalQueryItem(name=_row_get(r, "name", "") or "", kind="import", file_path=_row_get(r, "source_file", "") or "")
        for r in rows
    ]
    return LocalQueryResult(
        query_type="imports",
        title=f"Imports of {path}" if path else "Imports",
        count=len(items),
        items=items,
    )


def _counts_by_kind_runner(ctx: QueryContext, question: str) -> LocalQueryResult:
    rows = ctx.symbols.counts_by_kind()
    items = [
        LocalQueryItem(name=f"{_row_get(r, 'kind', '') or '(unknown)'}: {_row_get(r, 'c', 0)}", kind=_row_get(r, "kind", "") or "")
        for r in rows
    ]
    total = sum(int(_row_get(r, "c", 0) or 0) for r in rows)
    return LocalQueryResult(query_type="counts_by_kind", title="Symbol Counts by Type", count=total, items=items)


def _find_symbol_runner(ctx: QueryContext, question: str) -> LocalQueryResult:
    name = _extract_name(question)
    rows = ctx.symbols.search_by_name(name) if name else []
    items = [_symbol_item(r) for r in rows]
    return LocalQueryResult(
        query_type="find_symbol",
        title=f"Symbols matching '{name}'" if name else "Symbols",
        count=len(items),
        items=items,
    )


def _which_package_runner(ctx: QueryContext, question: str) -> LocalQueryResult:
    name = _extract_name(question)
    rows = ctx.symbols.find_by_name(name) if name else []
    items: list[LocalQueryItem] = []
    for r in rows:
        item = _symbol_item(r)
        items.append(item)
    return LocalQueryResult(
        query_type="which_package",
        title=f"Location of '{name}'" if name else "Location",
        count=len(items),
        items=items,
    )


def _where_is_runner(ctx: QueryContext, question: str) -> LocalQueryResult:
    """Generic 'where is X' handler — uses partial symbol matching.

    Works for any term: "where is VerificationController", "where is
    /api/verifications/{id}", "where is KafkaConsumer", etc.
    """

    name = _extract_name(question)
    if not name:
        return LocalQueryResult(query_type="where_is", title="Location", count=0)
    # Try exact match first, then fall back to partial (LIKE).
    rows = ctx.symbols.find_by_name(name, limit=50)
    if not rows:
        rows = ctx.symbols.search_by_name(name, limit=50)
    items = [_symbol_item(r) for r in rows]
    return LocalQueryResult(
        query_type="where_is",
        title=f"Location of '{name}'" if name else "Location",
        count=len(items),
        items=items,
    )


# -- handler registry -------------------------------------------------------
def default_handlers() -> list[LocalHandler]:
    """Return the Phase-1 handler registry, in priority order.

    Order matters: more specific matchers should precede generic ones.
    """

    def has(*words: str) -> Matcher:
        return lambda q: any(w in q for w in words)

    return [
        # "where is X" — generic symbol lookup, must precede stereotype
        # handlers so "where is VerificationController" is not swallowed by
        # the controller handler.
        LocalHandler("where_is", lambda q: q.startswith("where is") or q.startswith("where's"), _where_is_runner),
        # Explicit symbol lookup wins first so a name like "PaymentService" is
        # not mis-routed to the stereotype "service" handler.
        LocalHandler("which_package", has("which package", "what package", "package contains"), _which_package_runner),
        LocalHandler("find_symbol", lambda q: q.startswith("find ") or "symbol by name" in q or "methods named" in q, _find_symbol_runner),
        LocalHandler("counts_by_kind", has("count symbols", "symbols by type", "count by type", "symbol counts"), _counts_by_kind_runner, broad=True),
        # Grouped routes/endpoints must precede stereotype handlers so that
        # “show all routes grouped by controller” is not swallowed by the
        # generic controller handler just because “controller” appears.
        LocalHandler("grouped_routes", _is_grouped_symbols_query, _grouped_routes_runner, tag_dependent=True, broad=True),
        # Stereotype / tag-based (tag_dependent → stale-aware). These enumerate a
        # whole category, so they are ``broad``: a question naming a specific
        # entity bypasses them and is resolved by the retrieval/AI pipeline.
        LocalHandler("controllers", has("controller"), _tag_handler("controller", "Controllers"), tag_dependent=True, broad=True),
        LocalHandler("services", has("service"), _tag_handler("service", "Services"), tag_dependent=True, broad=True),
        LocalHandler("repositories", has("repositor"), _tag_handler("repository", "Repositories"), tag_dependent=True, broad=True),
        LocalHandler("components", has("@component", "components", "spring component"), _tag_handler("component", "Components"), tag_dependent=True, broad=True),
        # Routes / endpoints (structural).
        LocalHandler("routes", has("route", "endpoint", "rest api", "rest endpoint"), _routes_runner, broad=True),
        # Tests (structural — kind based).
        LocalHandler("tests", has("test class", "test method", "test cases", "tests", "@test"), _kind_runner("test", "Tests"), broad=True),
        # Relationships (structural).
        LocalHandler("implements", has("implement"), _edge_runner("implements", "Classes Implementing Interfaces"), broad=True),
        LocalHandler("extends", has("extend", "subclass", "inherit"), _edge_runner("extends", "Classes Extending a Class"), broad=True),
        LocalHandler("imports", has("import"), _imports_runner),
    ]
