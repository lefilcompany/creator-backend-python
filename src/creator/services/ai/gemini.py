from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import Any

import httpx
from google.genai import errors, types

from creator.config import Settings
from creator.integrations.gemini.client import create_gemini_client
from creator.integrations.gemini.exceptions import (
    GeminiAuthenticationError,
    GeminiBlockedContentError,
    GeminiInvalidResponseError,
    GeminiProviderError,
    GeminiQuotaError,
    GeminiTimeoutError,
    GeminiTransientError,
)
from creator.services.ai.provider import ProviderNotConfiguredError

logger = logging.getLogger(__name__)

TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
AUTH_STATUS_CODES = {401, 403}


class GeminiLLMProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[float], float] | None = None,
    ) -> None:
        if not settings.gemini_api_key:
            raise ProviderNotConfiguredError("GEMINI_API_KEY is required")
        self._settings = settings
        self._client = client if client is not None else create_gemini_client(settings)
        self._sleep = sleep
        self._jitter = jitter or (lambda delay: random.uniform(0, delay * 0.1))
        self.model = settings.gemini_text_model

    def generate_text(self, prompt: str, temperature: float = 0.7) -> str:
        started_at = time.perf_counter()
        last_error: GeminiProviderError | None = None

        for attempt in range(1, self._settings.gemini_retry_attempts + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=temperature),
                )
                text = self._normalize_response(response)
                duration_ms = int((time.perf_counter() - started_at) * 1000)
                logger.info(
                    "gemini_text_generation_success",
                    extra={
                        "model": self.model,
                        "attempt": attempt,
                        "duration_ms": duration_ms,
                        "text_size_chars": len(text),
                    },
                )
                return text
            except Exception as error:
                provider_error = self._classify_error(error)
                last_error = provider_error
                duration_ms = int((time.perf_counter() - started_at) * 1000)
                logger.warning(
                    "gemini_text_generation_failure",
                    extra={
                        "model": self.model,
                        "attempt": attempt,
                        "duration_ms": duration_ms,
                        "error_type": provider_error.__class__.__name__,
                        "retryable": provider_error.retryable,
                    },
                )
                if not provider_error.retryable or attempt >= self._settings.gemini_retry_attempts:
                    raise provider_error from error
                self._sleep(self._retry_delay(attempt))

        raise last_error or GeminiInvalidResponseError("Gemini text generation failed")

    def _normalize_response(self, response: Any) -> str:
        self._raise_if_blocked(response)

        try:
            direct_text = getattr(response, "text", None)
        except ValueError as error:
            raise GeminiInvalidResponseError("Gemini response did not include text") from error
        if isinstance(direct_text, str) and direct_text.strip():
            return direct_text.strip()

        parts_text: list[str] = []
        for part in self._response_parts(response):
            text = getattr(part, "text", None)
            if isinstance(text, str) and text.strip():
                parts_text.append(text.strip())
        if parts_text:
            return "\n".join(parts_text)

        raise GeminiInvalidResponseError("Gemini response did not include text")

    def _response_parts(self, response: Any) -> list[Any]:
        parts = getattr(response, "parts", None)
        if isinstance(parts, list):
            return parts

        collected_parts: list[Any] = []
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            candidate_parts = getattr(content, "parts", None)
            if isinstance(candidate_parts, list):
                collected_parts.extend(candidate_parts)
        return collected_parts

    def _raise_if_blocked(self, response: Any) -> None:
        prompt_feedback = getattr(response, "prompt_feedback", None) or getattr(
            response,
            "promptFeedback",
            None,
        )
        block_reason = getattr(prompt_feedback, "block_reason", None) or getattr(
            prompt_feedback,
            "blockReason",
            None,
        )
        if block_reason:
            raise GeminiBlockedContentError("Gemini blocked the text prompt")

        for candidate in getattr(response, "candidates", []) or []:
            finish_reason = str(
                getattr(candidate, "finish_reason", None) or getattr(candidate, "finishReason", "")
            ).upper()
            if finish_reason in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
                raise GeminiBlockedContentError("Gemini blocked the text response")

    def _classify_error(self, error: Exception) -> GeminiProviderError:
        if isinstance(error, GeminiProviderError):
            return error
        if isinstance(error, (TimeoutError, httpx.TimeoutException)):
            return GeminiTimeoutError("Gemini request timed out", retryable=True)
        if isinstance(error, (httpx.ConnectError, httpx.NetworkError)):
            return GeminiTransientError("Gemini network request failed", retryable=True)
        if isinstance(error, errors.APIError):
            code = int(getattr(error, "code", 0) or 0)
            if code in AUTH_STATUS_CODES:
                return GeminiAuthenticationError("Gemini authentication failed")
            if code == 429:
                return GeminiQuotaError("Gemini quota or rate limit exceeded", retryable=True)
            if code == 408:
                return GeminiTimeoutError("Gemini request timed out", retryable=True)
            if code in TRANSIENT_STATUS_CODES:
                return GeminiTransientError("Gemini transient provider error", retryable=True)
            return GeminiProviderError("Gemini provider rejected the request")
        return GeminiProviderError("Gemini provider request failed")

    def _retry_delay(self, completed_attempt: int) -> float:
        base_delay = float(self._settings.gemini_retry_initial_delay_seconds) * (
            2 ** (completed_attempt - 1)
        )
        capped_delay = min(base_delay, float(self._settings.gemini_retry_max_delay_seconds))
        return float(capped_delay + self._jitter(capped_delay))
