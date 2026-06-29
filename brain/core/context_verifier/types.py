"""Types used by the context verifier pipeline."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from brain.types.brain_types import CamelModel


QuestionType = Literal["explanation", "implementation", "debugging", "review", "unknown"]
Intensity = Literal["low", "medium", "high"]
Answerable = Literal["yes", "partial", "no"]
EdgeKind = Literal["import", "call", "reference", "route", "test", "unknown"]


class ContextIntentResult(CamelModel):
    original_question: str
    rewritten_queries: list[str] = []
    question_type: QuestionType = "unknown"
    intensity: Intensity = "medium"
    needs_main_ai: bool = True
    reason: str = ""


class RetrievedChunk(CamelModel):
    id: str
    file_path: str
    symbol_name: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    content: str
    score: Optional[float] = None
    source: Optional[str] = None


class ChunkGraphNode(CamelModel):
    id: str
    file_path: str
    symbol_name: Optional[str] = None
    kind: Optional[str] = None


class ChunkGraphEdge(CamelModel):
    from_: str = Field(alias="from")
    to: str
    type: EdgeKind = "unknown"
    evidence: Optional[str] = None


class ChunkGraph(CamelModel):
    nodes: list[ChunkGraphNode] = []
    edges: list[ChunkGraphEdge] = []
    unresolved_references: list[str] = []


class ContextVerificationResult(CamelModel):
    answerable: Answerable = "partial"
    confidence: float = 0.0
    keep_chunk_ids: list[str] = []
    remove_chunk_ids: list[str] = []
    missing_symbols: list[str] = []
    missing_files: list[str] = []
    followup_queries: list[str] = []
    reason: str = ""
    explanation: Optional[str] = None


class FinalVerifiedContext(CamelModel):
    original_question: str
    question_type: str
    attempts: int
    confidence: float
    answerable: Answerable
    packed_chunks: list[RetrievedChunk] = []
    removed_chunks: list[RetrievedChunk] = []
    missing_symbols: list[str] = []
    missing_files: list[str] = []
    graph: ChunkGraph = Field(default_factory=ChunkGraph)
    logs: list[str] = []
    explanation: Optional[str] = None

