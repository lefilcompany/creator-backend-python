from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import httpx
from google.genai import errors, types
from PIL import Image as PillowImage
from PIL import UnidentifiedImageError

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

logger = logging.getLogger(__name__)

TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
AUTH_STATUS_CODES = {401, 403}
SUPPORTED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}


@dataclass(frozen=True, slots=True)
class GeminiImageGenerationRequest:
    prompt: str
    model: str | None = None
    output_mime_type: str = "image/png"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GeminiImageGenerationResult:
    image_bytes: bytes
    mime_type: str
    width: int
    height: int
    model: str
    prompt: str
    metadata: dict[str, object]


class GeminiImageGenerator:
    def __init__(
        self,
        settings: Settings,
        *,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[float], float] | None = None,
    ) -> None:
        self._settings = settings
        self._client = client if client is not None else create_gemini_client(settings)
        self._sleep = sleep
        self._jitter = jitter or (lambda delay: random.uniform(0, delay * 0.1))

    def generate(self, request: GeminiImageGenerationRequest) -> GeminiImageGenerationResult:
        if request.output_mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
            raise GeminiInvalidResponseError("Unsupported requested image mime type")

        model = request.model or self._settings.gemini_image_model
        started_at = time.perf_counter()
        last_error: GeminiProviderError | None = None

        for attempt in range(1, self._settings.gemini_retry_attempts + 1):
            try:
                response = self._generate_content(model, request)
                result = self._normalize_response(response, model, request)
                duration_ms = int((time.perf_counter() - started_at) * 1000)
                logger.info(
                    "gemini_image_generation_success",
                    extra={
                        "model": model,
                        "attempt": attempt,
                        "duration_ms": duration_ms,
                        "mime_type": result.mime_type,
                        "image_size_bytes": len(result.image_bytes),
                    },
                )
                return result
            except Exception as error:
                provider_error = self._classify_error(error)
                last_error = provider_error
                duration_ms = int((time.perf_counter() - started_at) * 1000)
                logger.warning(
                    "gemini_image_generation_failure",
                    extra={
                        "model": model,
                        "attempt": attempt,
                        "duration_ms": duration_ms,
                        "error_type": provider_error.__class__.__name__,
                        "retryable": provider_error.retryable,
                    },
                )
                if not provider_error.retryable or attempt >= self._settings.gemini_retry_attempts:
                    raise provider_error from error
                self._sleep(self._retry_delay(attempt))

        raise last_error or GeminiInvalidResponseError("Gemini image generation failed")

    def _generate_content(
        self,
        model: str,
        request: GeminiImageGenerationRequest,
    ) -> Any:
        return self._client.models.generate_content(
            model=model,
            contents=self._structured_prompt(request),
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                response_mime_type=request.output_mime_type,
            ),
        )

    def _structured_prompt(self, request: GeminiImageGenerationRequest) -> str:
        return (
            "Generate a single marketing image for Creator.\n"
            "Return image output only.\n"
            f"Prompt:\n{request.prompt}"
        )

    def _normalize_response(
        self,
        response: Any,
        model: str,
        request: GeminiImageGenerationRequest,
    ) -> GeminiImageGenerationResult:
        self._raise_if_blocked(response)
        for part in self._response_parts(response):
            inline_data = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
            if inline_data is None:
                continue
            image_bytes = getattr(inline_data, "data", None)
            mime_type = getattr(inline_data, "mime_type", None) or getattr(
                inline_data, "mimeType", None
            )
            if not isinstance(image_bytes, bytes) or not isinstance(mime_type, str):
                continue
            if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
                raise GeminiInvalidResponseError("Gemini returned an unsupported image mime type")
            width, height, normalized_mime_type = self._inspect_image(image_bytes, mime_type)
            metadata = {
                "provider": "gemini",
                "source_model": model,
                "output_mime_type": normalized_mime_type,
                **request.metadata,
            }
            return GeminiImageGenerationResult(
                image_bytes=image_bytes,
                mime_type=normalized_mime_type,
                width=width,
                height=height,
                model=model,
                prompt=request.prompt,
                metadata=metadata,
            )
        raise GeminiInvalidResponseError("Gemini response did not include image bytes")

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
            response, "promptFeedback", None
        )
        block_reason = getattr(prompt_feedback, "block_reason", None) or getattr(
            prompt_feedback, "blockReason", None
        )
        if block_reason:
            raise GeminiBlockedContentError("Gemini blocked the image prompt")

        for candidate in getattr(response, "candidates", []) or []:
            finish_reason = str(
                getattr(candidate, "finish_reason", None) or getattr(candidate, "finishReason", "")
            ).upper()
            if finish_reason in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
                raise GeminiBlockedContentError("Gemini blocked the image response")

    def _inspect_image(self, image_bytes: bytes, mime_type: str) -> tuple[int, int, str]:
        try:
            with PillowImage.open(BytesIO(image_bytes)) as image:
                width, height = image.size
                detected_mime_type = PillowImage.MIME.get(image.format or "", mime_type)
        except UnidentifiedImageError as error:
            raise GeminiInvalidResponseError("Gemini returned invalid image bytes") from error
        if width <= 0 or height <= 0:
            raise GeminiInvalidResponseError("Gemini returned invalid image dimensions")
        if detected_mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
            raise GeminiInvalidResponseError("Gemini returned unsupported image bytes")
        return width, height, detected_mime_type

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
