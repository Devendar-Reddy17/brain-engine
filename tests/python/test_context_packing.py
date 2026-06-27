from brain.core.retrieval.context_packer import pack
from brain.core.retrieval.context_retriever import RetrievalResult
from brain.types.brain_types import (
    ContextChunk,
    DependencyContext,
    Intent,
    RelevantFile,
    TargetSymbol,
    TokenSavings,
)


def _result() -> RetrievalResult:
    return RetrievalResult(
        prompt="where is login implemented?",
        intent=Intent.QUESTION,
        confidence=0.72,
        confidence_reason="context is likely sufficient (strong top match).",
        token_savings=TokenSavings(repo_tokens=425000, context_tokens=18200, reduction_percentage=95.7),
        relevant_files=[RelevantFile(path="src/LoginController.java", reason="exact symbol match")],
        target_symbols=[
            TargetSymbol(name="login", kind="route", file="src/LoginController.java", start_line=10, end_line=20)
        ],
        chunks=[
            ContextChunk(
                file="src/LoginController.java", symbol="login", start_line=10, end_line=20,
                reason="exact symbol match", content="public String login() { return ok; }",
            )
        ],
        dependency_context=DependencyContext(callers=["AuthFilter"], tests=["testLogin"]),
        git_diff_summary=None,
        missing_context_warnings=[],
    )


def test_pack_contains_required_sections():
    md = pack(_result())
    for header in (
        "# User Task",
        "# Intent",
        "# Confidence",
        "# Token Savings",
        "# Relevant Files",
        "# Target Symbols",
        "# Context Chunks",
        "# Dependency Context",
        "# Current Git Diff",
        "# Missing Context Warnings",
        "# Instructions To AI Agent",
    ):
        assert header in md, f"missing section {header}"


def test_token_savings_appears_immediately_after_confidence():
    md = pack(_result())
    confidence_idx = md.index("# Confidence")
    token_idx = md.index("# Token Savings")
    files_idx = md.index("# Relevant Files")
    assert confidence_idx < token_idx < files_idx


def test_token_savings_values_formatted():
    md = pack(_result())
    assert "Estimated Full Repo Tokens: 425,000" in md
    assert "Packed Context Tokens: 18,200" in md
    assert "Estimated Reduction: 95.7%" in md
