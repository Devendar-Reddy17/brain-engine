"""FastAPI application exposing the brain engine over localhost HTTP."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from brain.daemon.lifecycle import AskOutcome, BrainEngine
from brain.daemon.models import (
    AskRequest,
    AskResponse,
    ContextRequest,
    ContextResponse,
    EnqueueChangeRequest,
    GitRefreshRequest,
    GitRefreshResponse,
    HealthResponse,
    IndexRequest,
    IndexResponse,
    StatusResponse,
    WatchStateResponse,
)
from brain.types.brain_types import LocalQueryGroup, LocalQueryItem, LocalQueryResult
from brain.utils.logger import get_logger

log = get_logger(__name__)


def create_app(engine: BrainEngine) -> FastAPI:
    app = FastAPI(title="Local Code Brain Daemon", version=engine.version())

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(version=engine.version(), repo_root=engine.repo_root)

    @app.post("/index", response_model=IndexResponse)
    def index(_: IndexRequest) -> IndexResponse:
        result = engine.run_full_index()
        return IndexResponse(
            repo_root=result.repo_root,
            files_scanned=result.files_scanned,
            files_indexed=result.files_indexed,
            files_skipped=result.files_skipped,
            chunks_created=result.chunks_created,
            symbols_extracted=result.symbols_extracted,
            duration_ms=result.duration_ms,
            forced=result.forced,
            total_files=result.total_files,
            total_chunks=result.total_chunks,
            total_symbols=result.total_symbols,
        )

    @app.get("/status", response_model=StatusResponse)
    def status() -> StatusResponse:
        s = engine.status()
        return StatusResponse(
            repo_root=s["repo_root"],
            indexed_files=s["indexed_files"],
            chunks=s["chunks"],
            symbols=s["symbols"],
            last_full_index_at=s["last_full_index_at"],
            last_incremental_index_at=s["last_incremental_index_at"],
            pending_queue_size=s["pending_queue_size"],
            current_branch=s["current_branch"],
            fresh=s["fresh"],
            stale=s["stale"],
            stale_reason=s["stale_reason"],
        )

    @app.post("/context", response_model=ContextResponse)
    def context(req: ContextRequest) -> ContextResponse:
        # Kept for backward compatibility / internal use. New clients should
        # call /ask, the single public entry point for repository questions.
        result = engine.retrieve_context(req.prompt, req.intent, req.include_full_diff)
        return _to_context_response(result)

    @app.post("/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> AskResponse:
        outcome: AskOutcome = engine.ask(req.question, req.repo_path)
        if outcome.execution_path == "local" and outcome.local_result is not None:
            return AskResponse(
                execution_path="local",
                result=_to_local_query_result(outcome.local_result),
            )
        return AskResponse(
            execution_path="ai_required",
            context=_to_context_response(outcome.retrieval),
        )

    @app.post("/git-refresh", response_model=GitRefreshResponse)
    def git_refresh(_: GitRefreshRequest) -> GitRefreshResponse:
        count, files = engine.git_refresh()
        return GitRefreshResponse(enqueued=count, files=files)

    @app.post("/changes/enqueue", response_model=WatchStateResponse)
    def enqueue(req: EnqueueChangeRequest) -> WatchStateResponse:
        engine.enqueue_changes(req.paths, req.event_type, req.priority)
        return WatchStateResponse(
            watching=engine.is_watching(),
            pending_queue_size=engine.queue_repo.pending_count(),
        )

    @app.post("/watch/start", response_model=WatchStateResponse)
    def watch_start() -> WatchStateResponse:
        engine.start_watch()
        return WatchStateResponse(
            watching=engine.is_watching(),
            pending_queue_size=engine.queue_repo.pending_count(),
        )

    @app.post("/watch/stop", response_model=WatchStateResponse)
    def watch_stop() -> WatchStateResponse:
        engine.stop_watch()
        return WatchStateResponse(
            watching=engine.is_watching(),
            pending_queue_size=engine.queue_repo.pending_count(),
        )

    def _to_context_response(result) -> ContextResponse:
        ts = result.token_savings
        # Logging per spec.
        log.info("Repository Tokens: %d", ts.repo_tokens)
        log.info("Context Tokens: %d", ts.context_tokens)
        log.info("Token Reduction: %.1f%%", ts.reduction_percentage)
        return ContextResponse(
            markdown=result.markdown,
            prompt=result.prompt,
            intent=result.intent,
            confidence=result.confidence,
            confidence_reason=result.confidence_reason,
            token_savings=ts,
            relevant_files=result.relevant_files,
            target_symbols=result.target_symbols,
            chunks=result.chunks,
            dependency_context=result.dependency_context,
            git_diff_summary=result.git_diff_summary,
            missing_context_warnings=result.missing_context_warnings,
            verifier_explanation=getattr(result, "verifier_explanation", None),
            verifier_needs_main_ai=getattr(result, "verifier_needs_main_ai", None),
            verifier_question_type=getattr(result, "verifier_question_type", None),
        )

    def _to_local_query_result(result) -> LocalQueryResult:
        return LocalQueryResult(
            query_type=result.query_type,
            title=result.title,
            count=result.count,
            items=[
                LocalQueryItem(
                    name=i.name,
                    kind=i.kind,
                    file_path=i.file_path,
                    start_line=i.start_line,
                    end_line=i.end_line,
                    parent_symbol=i.parent_symbol,
                    annotations=i.annotations,
                    tags=i.tags,
                )
                for i in result.items
            ],
            groups=[
                LocalQueryGroup(
                    owner=g.owner,
                    owner_kind=g.owner_kind,
                    owner_file=g.owner_file,
                    items=[
                        LocalQueryItem(
                            name=i.name,
                            kind=i.kind,
                            file_path=i.file_path,
                            start_line=i.start_line,
                            end_line=i.end_line,
                            parent_symbol=i.parent_symbol,
                            annotations=i.annotations,
                            tags=i.tags,
                        )
                        for i in g.items
                    ],
                )
                for g in result.groups
            ],
            stale_warning=result.stale_warning,
        )

    @app.exception_handler(Exception)
    async def on_error(_, exc: Exception) -> JSONResponse:  # pragma: no cover
        log.exception("Unhandled error: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)})

    return app
