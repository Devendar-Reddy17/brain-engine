"""Pydantic request/response models for the FastAPI daemon.

These mirror ``packages/shared/src/schemas/apiSchemas.ts``. All models use
camelCase JSON aliases (via :class:`CamelModel`) so the wire format matches the
TypeScript contracts. The context response includes the ``tokenSavings`` block.
"""

from __future__ import annotations

from typing import Optional

from brain.types.brain_types import (
    CamelModel,
    ContextChunk,
    DependencyContext,
    Intent,
    LocalQueryResult,
    RelevantFile,
    TargetSymbol,
    TokenSavings,
)


class HealthResponse(CamelModel):
    status: str = "ok"
    version: str
    repo_root: Optional[str] = None


class IndexRequest(CamelModel):
    repo_root: Optional[str] = None
    full: bool = True


class IndexResponse(CamelModel):
    repo_root: str
    files_scanned: int
    files_indexed: int
    files_skipped: int
    chunks_created: int
    symbols_extracted: int
    duration_ms: int
    forced: bool = False
    total_files: int = 0
    total_chunks: int = 0
    total_symbols: int = 0


class StatusResponse(CamelModel):
    repo_root: str
    indexed_files: int
    chunks: int
    symbols: int
    last_full_index_at: Optional[str] = None
    last_incremental_index_at: Optional[str] = None
    pending_queue_size: int
    current_branch: Optional[str] = None
    fresh: bool
    stale: bool = False
    stale_reason: Optional[str] = None


class ContextRequest(CamelModel):
    prompt: str
    intent: Optional[Intent] = None
    include_full_diff: bool = False


class ContextResponse(CamelModel):
    markdown: str
    prompt: str
    intent: Intent
    confidence: float
    confidence_reason: str
    token_savings: TokenSavings
    relevant_files: list[RelevantFile] = []
    target_symbols: list[TargetSymbol] = []
    chunks: list[ContextChunk] = []
    dependency_context: DependencyContext = DependencyContext()
    git_diff_summary: Optional[str] = None
    missing_context_warnings: list[str] = []
    verifier_explanation: Optional[str] = None
    verifier_needs_main_ai: Optional[bool] = None
    verifier_question_type: Optional[str] = None


class AskRequest(CamelModel):
    """Public ask contract used by every client (CLI/MCP/IDE/web)."""

    question: str
    repo_path: Optional[str] = None


class AskResponse(CamelModel):
    """Routing result. Clients only need ``executionPath``.

    * ``local``       -> ``result`` holds the structured answer.
    * ``ai_required`` -> ``context`` holds the context package for the client's
      AI pipeline (Phase 1: orchestration stays client-side).
    """

    execution_path: str  # "local" | "ai_required"
    result: Optional[LocalQueryResult] = None
    context: Optional["ContextResponse"] = None


class GitRefreshRequest(CamelModel):
    repo_root: Optional[str] = None


class GitRefreshResponse(CamelModel):
    enqueued: int
    files: list[str] = []


class EnqueueChangeRequest(CamelModel):
    paths: list[str]
    event_type: str = "modified"
    priority: Optional[int] = None


class WatchStateResponse(CamelModel):
    watching: bool
    pending_queue_size: int


class ErrorResponse(CamelModel):
    error: str
    detail: Optional[str] = None
