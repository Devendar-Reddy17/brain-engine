import os

import pytest

from brain.config.default_config import ContextVerifierSection
from brain.core.context_verifier.graph import build_chunk_graph
from brain.core.context_verifier.json_utils import parse_json_object
from brain.core.context_verifier.packing import merge_and_dedupe_chunks, retrieved_chunks_from_result
from brain.core.context_verifier.pipeline import ContextVerifierPipeline
from brain.core.context_verifier.provider import create_provider
from brain.core.context_verifier.types import (
    ChunkGraph,
    ContextIntentResult,
    ContextVerificationResult,
    RetrievedChunk,
)
from brain.core.retrieval.context_retriever import RetrievalResult
from brain.types.brain_types import ContextChunk, DependencyContext, Intent, TokenSavings


def _chunk(
    file_path: str,
    symbol: str | None,
    content: str,
    start: int = 1,
    end: int = 3,
) -> ContextChunk:
    return ContextChunk(
        file=file_path,
        symbol=symbol,
        start_line=start,
        end_line=end,
        reason="test",
        content=content,
    )


def _result(chunks: list[ContextChunk]) -> RetrievalResult:
    return RetrievalResult(
        prompt="explain login",
        intent=Intent.QUESTION,
        confidence=0.5,
        confidence_reason="test",
        token_savings=TokenSavings(repo_tokens=1000, context_tokens=100, reduction_percentage=90.0),
        chunks=chunks,
        dependency_context=DependencyContext(),
    )


def test_parse_json_extracts_fenced_block():
    parsed = parse_json_object('noise\n```json\n{"answerable":"yes","confidence":0.8}\n```\nmore')
    assert parsed["answerable"] == "yes"
    assert parsed["confidence"] == 0.8


def test_parse_json_extracts_embedded_object():
    parsed = parse_json_object('model said: {"keepChunkIds":["a"],"reason":"ok"} thanks')
    assert parsed["keepChunkIds"] == ["a"]


def test_merge_and_dedupe_chunks_uses_file_lines_and_content():
    chunk = RetrievedChunk(id="a", file_path="src/a.py", start_line=1, end_line=2, content="print(1)")
    duplicate = RetrievedChunk(id="b", file_path="src/a.py", start_line=1, end_line=2, content="print(1)")
    other = RetrievedChunk(id="c", file_path="src/a.py", start_line=3, end_line=4, content="print(1)")

    merged = merge_and_dedupe_chunks([chunk], [duplicate, other])

    assert [c.id for c in merged] == ["a", "c"]


def test_build_chunk_graph_detects_import_reference_route_and_unresolved():
    controller = RetrievedChunk(
        id="controller",
        file_path="src/LoginController.java",
        symbol_name="LoginController",
        content="import com.example.AuthService;\n@GetMapping(\"/login\")\nclass LoginController { AuthService svc; }",
    )
    service = RetrievedChunk(
        id="service",
        file_path="src/AuthService.java",
        symbol_name="AuthService",
        content="class AuthService {}",
    )

    graph = build_chunk_graph([controller, service])

    assert any(edge.type == "import" and edge.to == "service" for edge in graph.edges)
    assert any(edge.type in {"reference", "route"} and edge.to == "service" for edge in graph.edges)
    assert "com.example.AuthService" not in graph.unresolved_references


def test_pipeline_stops_at_max_three_attempts():
    class FakeProvider:
        verify_calls = 0

        def analyse_intent(self, question: str) -> ContextIntentResult:
            return ContextIntentResult(
                originalQuestion=question,
                rewrittenQueries=["LoginController"],
                questionType="explanation",
                intensity="medium",
                needsMainAI=False,
                reason="test",
            )

        def verify(
            self,
            *,
            question: str,
            intent: ContextIntentResult,
            chunks: list[RetrievedChunk],
            graph: ChunkGraph,
            attempt: int,
            max_attempts: int,
        ) -> ContextVerificationResult:
            self.verify_calls += 1
            return ContextVerificationResult(
                answerable="partial",
                confidence=0.2,
                keepChunkIds=[chunks[0].id],
                followupQueries=[f"followup {attempt}"],
                reason="missing",
            )

    provider = FakeProvider()
    calls: list[str] = []

    def retrieve(query: str) -> RetrievalResult:
        calls.append(query)
        return _result([_chunk("src/LoginController.java", "LoginController", f"class LoginController {{ {query} }}")])

    config = ContextVerifierSection(enabled=True, maxAttempts=3)
    result = ContextVerifierPipeline(config, retrieve, provider).run("explain login")

    assert provider.verify_calls == 3
    assert any("finalPackedChunks=" in line for line in result.verifier_logs)
    assert len(retrieved_chunks_from_result(result)) == 1


def test_missing_api_key_provider_fails_without_crashing_pipeline(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    config = ContextVerifierSection(enabled=True, apiKeyEnv="OPENROUTER_API_KEY")

    with pytest.raises(RuntimeError):
        # Direct provider construction reports the missing key.
        create_provider(config)

    def retrieve(_: str) -> RetrievalResult:
        return _result([_chunk("src/a.py", "a", "def a(): pass")])

    result = ContextVerifierPipeline(config, retrieve).run("explain a")

    assert result.chunks
    assert any("OPENROUTER_API_KEY not found" in line for line in result.verifier_logs)
