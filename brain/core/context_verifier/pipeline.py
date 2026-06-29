"""Flow-aware context verifier pipeline."""

from __future__ import annotations

from collections.abc import Callable

from brain.config.default_config import ContextVerifierSection
from brain.core.context_verifier.graph import build_chunk_graph
from brain.core.context_verifier.packing import (
    apply_verified_chunks,
    merge_and_dedupe_chunks,
    pack_chunks,
    retrieved_chunks_from_result,
)
from brain.core.context_verifier.provider import (
    ContextVerifierProvider,
    MissingVerifierApiKey,
    create_provider,
)
from brain.core.context_verifier.types import (
    ChunkGraph,
    ContextIntentResult,
    ContextVerificationResult,
    FinalVerifiedContext,
    RetrievedChunk,
)
from brain.core.retrieval.context_retriever import RetrievalResult
from brain.utils.logger import get_logger

log = get_logger(__name__)

RetrieveFn = Callable[[str], RetrievalResult]


class ContextVerifierPipeline:
    def __init__(
        self,
        config: ContextVerifierSection,
        retrieve: RetrieveFn,
        provider: ContextVerifierProvider | None = None,
    ) -> None:
        self.config = config
        self.retrieve = retrieve
        self.provider = provider

    def run(self, question: str) -> RetrievalResult:
        logs = [
            f"[ContextVerifier] enabled=true provider={self.config.provider} model={self.config.model}"
        ]
        try:
            provider = self.provider or create_provider(self.config)
        except MissingVerifierApiKey:
            logs.append(f"Context verifier disabled: {self.config.api_key_env} not found")
            result = self.retrieve(question)
            result.verifier_logs = logs
            return result
        except Exception as exc:
            logs.append(f"[ContextVerifier] disabled: provider setup failed: {exc}")
            result = self.retrieve(question)
            result.verifier_logs = logs
            return result

        try:
            final, result = self._run_verified(question, provider, logs)
            apply_verified_chunks(result, final.packed_chunks)
            result.confidence = final.confidence
            result.confidence_reason = final.logs[-1] if final.logs else result.confidence_reason
            result.missing_context_warnings.extend(_missing_warnings(final))
            result.verifier_logs = final.logs
            result.verifier_explanation = final.explanation
            result.verifier_question_type = final.question_type
            result.verifier_needs_main_ai = final.needs_main_ai
            return result
        except Exception as exc:
            logs.append(f"[ContextVerifier] failed: {exc}; falling back to current retrieval")
            log.warning("Context verifier failed; falling back to current retrieval: %s", exc)
            result = self.retrieve(question)
            result.verifier_logs = logs
            return result

    def _run_verified(
        self,
        question: str,
        provider: ContextVerifierProvider,
        logs: list[str],
    ) -> tuple[FinalVerifiedContext, RetrievalResult]:
        intent = provider.analyse_intent(question)
        intent.original_question = question
        logs.append(
            f"[ContextVerifier] intent={intent.question_type} intensity={intent.intensity} "
            f"needsMainAI={str(intent.needs_main_ai).lower()}"
        )

        max_attempts = max(1, min(3, self.config.max_attempts))
        min_confidence = self.config.min_confidence
        queries = _dedupe_text([question, *intent.rewritten_queries])
        all_chunks: list[RetrievedChunk] = []
        removed_chunks: list[RetrievedChunk] = []
        final_verification = ContextVerificationResult()
        final_graph = ChunkGraph()
        attempts = 0
        last_result: RetrievalResult | None = None

        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            retrieved_this_attempt: list[RetrievedChunk] = []
            for query in queries:
                last_result = self.retrieve(query)
                retrieved_this_attempt = merge_and_dedupe_chunks(
                    retrieved_this_attempt,
                    retrieved_chunks_from_result(last_result),
                )

            before_count = len(all_chunks)
            all_chunks = merge_and_dedupe_chunks(all_chunks, retrieved_this_attempt)
            final_graph = build_chunk_graph(all_chunks)
            verification = provider.verify(
                question=question,
                intent=intent,
                chunks=all_chunks,
                graph=final_graph,
                attempt=attempt,
                max_attempts=max_attempts,
            )
            verification = _sanitize_verification(verification, all_chunks, attempt, max_attempts, intent)
            final_verification = verification

            remove_ids = set(verification.remove_chunk_ids)
            removed_now = [chunk for chunk in all_chunks if chunk.id in remove_ids]
            removed_chunks = merge_and_dedupe_chunks(removed_chunks, removed_now)
            all_chunks = [chunk for chunk in all_chunks if chunk.id not in remove_ids]

            logs.append(
                f"[ContextVerifier] attempt={attempt} retrieved={len(retrieved_this_attempt)} "
                f"kept={len(verification.keep_chunk_ids)} removed={len(removed_now)} "
                f"missing={len(verification.missing_symbols) + len(verification.missing_files)} "
                f"confidence={verification.confidence:.2f}"
            )
            if verification.followup_queries:
                logs.append(f"[ContextVerifier] followupQueries={verification.followup_queries}")

            if verification.answerable == "yes" and verification.confidence >= min_confidence:
                break
            if attempt == max_attempts or not verification.followup_queries:
                break
            if len(all_chunks) == before_count and not verification.followup_queries:
                break
            queries = _dedupe_text(verification.followup_queries)

        packed = pack_chunks(all_chunks, final_verification.keep_chunk_ids)
        logs.append(
            f"[ContextVerifier] finalPackedChunks={len(packed)} "
            f"answerable={final_verification.answerable}"
        )
        if packed:
            logs.append(
                "[ContextVerifier] finalFiles="
                + ", ".join(_dedupe_text([chunk.file_path for chunk in packed]))
            )

        result = last_result or self.retrieve(question)
        result.prompt = question
        return (
            FinalVerifiedContext(
                original_question=question,
                question_type=intent.question_type,
                needs_main_ai=intent.needs_main_ai,
                attempts=attempts,
                confidence=final_verification.confidence,
                answerable=final_verification.answerable,
                packed_chunks=packed,
                removed_chunks=removed_chunks,
                missing_symbols=final_verification.missing_symbols,
                missing_files=final_verification.missing_files,
                graph=final_graph,
                logs=logs,
                explanation=final_verification.explanation
                if self.config.explain_with_verifier and intent.question_type == "explanation"
                else None,
            ),
            result,
        )


def _sanitize_verification(
    verification: ContextVerificationResult,
    chunks: list[RetrievedChunk],
    attempt: int,
    max_attempts: int,
    intent: ContextIntentResult,
) -> ContextVerificationResult:
    known_ids = {chunk.id for chunk in chunks}
    verification.keep_chunk_ids = [cid for cid in verification.keep_chunk_ids if cid in known_ids]
    verification.remove_chunk_ids = [cid for cid in verification.remove_chunk_ids if cid in known_ids]
    verification.confidence = max(0.0, min(1.0, verification.confidence))
    if attempt >= max_attempts:
        verification.followup_queries = []
    if intent.question_type != "explanation":
        verification.explanation = None
    return verification


def _missing_warnings(final: FinalVerifiedContext) -> list[str]:
    warnings: list[str] = []
    for symbol in final.missing_symbols:
        warnings.append(f"Context verifier missing symbol: {symbol}")
    for file_path in final.missing_files:
        warnings.append(f"Context verifier missing file: {file_path}")
    return warnings


def _dedupe_text(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out
