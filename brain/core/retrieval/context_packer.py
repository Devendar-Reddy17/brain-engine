"""Pack a :class:`RetrievalResult` into the markdown context package.

Section order follows the spec exactly, with the **Token Savings** section
inserted immediately after **Confidence**.
"""

from __future__ import annotations

from brain.core.retrieval.context_retriever import RetrievalResult
from brain.types.brain_types import Intent


def _fmt(n: int) -> str:
    return f"{n:,}"


def pack(result: RetrievalResult) -> str:
    p: list[str] = []

    p.append("# User Task\n")
    p.append(result.prompt.strip() + "\n")

    p.append("# Intent\n")
    p.append(result.intent.value + "\n")

    p.append("# Confidence\n")
    p.append(f"Score: {result.confidence:.2f}")
    p.append(f"Reason: {result.confidence_reason}\n")

    # Token Savings — immediately after Confidence (per spec).
    ts = result.token_savings
    if ts is not None:
        p.append("# Token Savings\n")
        p.append(f"Estimated Full Repo Tokens: {_fmt(ts.repo_tokens)}\n")
        p.append(f"Packed Context Tokens: {_fmt(ts.context_tokens)}\n")
        p.append(f"Estimated Reduction: {ts.reduction_percentage}%\n")
        p.append(_token_savings_reason(result))

    p.append("# Relevant Files\n")
    if result.relevant_files:
        for rf in result.relevant_files:
            p.append(f"* {rf.path}\n  * {rf.reason}")
    else:
        p.append("* (none)")
    p.append("")

    p.append("# Target Symbols\n")
    if result.target_symbols:
        for sym in result.target_symbols:
            p.append(f"* {sym.name} ({sym.kind}) — {sym.file}:{sym.start_line}-{sym.end_line}")
    else:
        p.append("* (none)")
    p.append("")

    p.append("# Context Chunks\n")
    if result.chunks:
        for chunk in result.chunks:
            p.append("```text")
            p.append(f"File: {chunk.file}")
            p.append(f"Symbol: {chunk.symbol or '(file)'}")
            p.append(f"Lines: {chunk.start_line}-{chunk.end_line}")
            p.append(f"Reason: {chunk.reason}")
            p.append("Content:")
            p.append(chunk.content)
            p.append("```")
            p.append("")
    else:
        p.append("(no chunks)\n")

    dc = result.dependency_context
    p.append("# Dependency Context\n")
    p.append(_dep_line("callers", dc.callers))
    p.append(_dep_line("callees", dc.callees))
    p.append(_dep_line("interfaces", dc.interfaces))
    p.append(_dep_line("implementations", dc.implementations))
    p.append(_dep_line("configs", dc.configs))
    p.append(_dep_line("routes", dc.routes))
    p.append(_dep_line("tests", dc.tests))
    p.append("")

    p.append("# Current Git Diff\n")
    if result.git_diff_full:
        p.append("```diff")
        p.append(result.git_diff_full.strip())
        p.append("```")
    elif result.git_diff_summary:
        p.append("```text")
        p.append(result.git_diff_summary.strip())
        p.append("```")
    else:
        p.append("(no uncommitted changes)")
    p.append("")

    p.append("# Missing Context Warnings\n")
    if result.missing_context_warnings:
        for w in result.missing_context_warnings:
            p.append(f"* {w}")
    else:
        p.append("* None")
    p.append("")

    p.append("# Instructions To AI Agent\n")
    for instruction in _instructions(result.intent):
        p.append(f"* {instruction}")
    p.append("")

    return "\n".join(p).strip() + "\n"


def _token_savings_reason(result: RetrievalResult) -> str:
    files = len(result.relevant_files)
    services = sum(1 for s in result.target_symbols if (s.kind or "") in ("class", "interface", "enum"))
    routes = sum(1 for s in result.target_symbols if s.kind == "route")
    tests = sum(1 for s in result.target_symbols if s.kind == "test")
    lines = [
        "Reason:",
        "Context was reduced using:",
        "- symbol filtering",
        "- dependency graph expansion",
        "- semantic chunk retrieval",
        "- intent-aware selection",
        "- test/config inclusion rules",
        "",
        f"Only {files} relevant file(s), {services} type(s), {routes} route(s), "
        f"and {tests} test(s) were included.\n",
    ]
    return "\n".join(lines)


def _dep_line(label: str, values: list[str]) -> str:
    rendered = ", ".join(values) if values else "(none)"
    return f"* {label}: {rendered}"


def _instructions(intent: Intent) -> list[str]:
    base = [
        "Modify only relevant files.",
        "Preserve existing architecture.",
        "Do not invent missing APIs.",
        "Add/update tests when needed.",
        "Explain assumptions if context is incomplete.",
    ]
    if intent == Intent.CODE_EDIT:
        base.insert(2, "Return a unified diff only.")
    return base
