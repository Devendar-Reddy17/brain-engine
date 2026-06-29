"""Provider abstraction and OpenAI-compatible OpenRouter implementation."""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from brain.config.default_config import ContextVerifierSection
from brain.core.context_verifier.json_utils import parse_json_object
from brain.core.context_verifier.prompts import INTENT_SYSTEM, VERIFY_SYSTEM, intent_user, verify_user
from brain.core.context_verifier.types import (
    ChunkGraph,
    ContextIntentResult,
    ContextVerificationResult,
    RetrievedChunk,
)


class ContextVerifierProvider(ABC):
    @abstractmethod
    def analyse_intent(self, question: str) -> ContextIntentResult:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError


class MissingVerifierApiKey(RuntimeError):
    pass


class OpenAICompatibleVerifierProvider(ContextVerifierProvider):
    def __init__(self, config: ContextVerifierSection) -> None:
        self.config = config
        self.api_key = os.environ.get(config.api_key_env, "")
        if config.api_key_env and not self.api_key:
            raise MissingVerifierApiKey(config.api_key_env)

    def analyse_intent(self, question: str) -> ContextIntentResult:
        data = self._chat_json(
            [
                {"role": "system", "content": INTENT_SYSTEM},
                {"role": "user", "content": intent_user(question)},
            ]
        )
        data.setdefault("originalQuestion", question)
        if data.get("originalQuestion") != question:
            data["originalQuestion"] = question
        return ContextIntentResult.model_validate(data)

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
        data = self._chat_json(
            [
                {"role": "system", "content": VERIFY_SYSTEM},
                {
                    "role": "user",
                    "content": verify_user(
                        question=question,
                        intent=intent,
                        chunks=chunks,
                        graph=graph,
                        attempt=attempt,
                        max_attempts=max_attempts,
                    ),
                },
            ]
        )
        return ContextVerificationResult.model_validate(data)

    def _chat_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.1,
        }

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                return parse_json_object(content)
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    break
                if attempt < 2:
                    time.sleep(0.25 * (attempt + 1))
            except Exception as exc:
                last_error = exc
                break
        raise RuntimeError(f"Context verifier provider failed: {last_error}") from last_error


def create_provider(config: ContextVerifierSection) -> ContextVerifierProvider:
    if config.provider in {"openrouter", "openai-compatible", "hosted"}:
        return OpenAICompatibleVerifierProvider(config)
    raise ValueError(f"Unsupported context verifier provider: {config.provider}")

