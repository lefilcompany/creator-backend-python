from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors
from PIL import Image

from creator.config import Settings
from creator.integrations.gemini.client import create_gemini_client
from creator.integrations.gemini.exceptions import (
    GeminiAuthenticationError,
    GeminiBlockedContentError,
    GeminiInvalidResponseError,
    GeminiQuotaError,
    GeminiTimeoutError,
)
from creator.integrations.gemini.image_generator import (
    GeminiImageGenerationRequest,
    GeminiImageGenerator,
)
from tests.fakes.gemini import FakeGeminiImageGenerator

SENSITIVE_PROMPT = "launch campaign with confidential customer names"


class FakeModels:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes: list[Any]) -> None:
        self.models = FakeModels(outcomes)


def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 3), color="red").save(output, format="PNG")
    return output.getvalue()


def image_response(image_bytes: bytes | None = None, mime_type: str = "image/png") -> Any:
    return SimpleNamespace(
        parts=[
            SimpleNamespace(
                inline_data=SimpleNamespace(
                    data=image_bytes if image_bytes is not None else png_bytes(),
                    mime_type=mime_type,
                )
            )
        ],
        candidates=[],
    )


def test_create_gemini_client_requires_api_key() -> None:
    with pytest.raises(GeminiAuthenticationError):
        create_gemini_client(Settings(gemini_api_key=None))


def test_generate_success_normalizes_image_metadata_and_redacts_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeClient([image_response()])
    generator = GeminiImageGenerator(
        Settings(gemini_api_key="secret", gemini_image_model="gemini-image-test"),
        client=client,
        sleep=lambda delay: None,
        jitter=lambda delay: 0,
    )

    result = generator.generate(GeminiImageGenerationRequest(prompt=SENSITIVE_PROMPT))

    assert result.mime_type == "image/png"
    assert result.width == 2
    assert result.height == 3
    assert result.model == "gemini-image-test"
    assert result.prompt == SENSITIVE_PROMPT
    assert result.metadata["provider"] == "gemini"
    assert client.models.calls[0]["model"] == "gemini-image-test"
    assert client.models.calls[0]["config"].response_modalities == ["IMAGE"]
    assert SENSITIVE_PROMPT not in caplog.text
    assert result.image_bytes.hex() not in caplog.text
    assert "secret" not in caplog.text


def test_timeout_retries_until_success() -> None:
    sleeps: list[float] = []
    client = FakeClient([TimeoutError("slow"), TimeoutError("still slow"), image_response()])
    generator = GeminiImageGenerator(
        Settings(gemini_api_key="secret", gemini_retry_attempts=3),
        client=client,
        sleep=sleeps.append,
        jitter=lambda delay: 0,
    )

    result = generator.generate(GeminiImageGenerationRequest(prompt="image"))

    assert result.width == 2
    assert len(client.models.calls) == 3
    assert sleeps == [1.0, 2.0]


def test_timeout_raises_after_retry_limit() -> None:
    client = FakeClient([TimeoutError("slow"), TimeoutError("still slow")])
    generator = GeminiImageGenerator(
        Settings(gemini_api_key="secret", gemini_retry_attempts=2),
        client=client,
        sleep=lambda delay: None,
        jitter=lambda delay: 0,
    )

    with pytest.raises(GeminiTimeoutError):
        generator.generate(GeminiImageGenerationRequest(prompt="image"))

    assert len(client.models.calls) == 2


def test_quota_error_is_retried_and_classified() -> None:
    client = FakeClient([errors.APIError(429, {"error": {"message": "rate limit"}})])
    generator = GeminiImageGenerator(
        Settings(gemini_api_key="secret", gemini_retry_attempts=1),
        client=client,
        sleep=lambda delay: None,
        jitter=lambda delay: 0,
    )

    with pytest.raises(GeminiQuotaError) as error:
        generator.generate(GeminiImageGenerationRequest(prompt="image"))

    assert error.value.retryable is True


def test_blocked_content_does_not_retry() -> None:
    blocked_response = SimpleNamespace(
        prompt_feedback=SimpleNamespace(block_reason="SAFETY"),
        parts=[],
        candidates=[],
    )
    client = FakeClient([blocked_response, image_response()])
    generator = GeminiImageGenerator(
        Settings(gemini_api_key="secret", gemini_retry_attempts=3),
        client=client,
        sleep=lambda delay: None,
        jitter=lambda delay: 0,
    )

    with pytest.raises(GeminiBlockedContentError):
        generator.generate(GeminiImageGenerationRequest(prompt="blocked"))

    assert len(client.models.calls) == 1


def test_invalid_response_without_image_is_not_retried() -> None:
    client = FakeClient([SimpleNamespace(parts=[], candidates=[])])
    generator = GeminiImageGenerator(
        Settings(gemini_api_key="secret", gemini_retry_attempts=3),
        client=client,
        sleep=lambda delay: None,
        jitter=lambda delay: 0,
    )

    with pytest.raises(GeminiInvalidResponseError):
        generator.generate(GeminiImageGenerationRequest(prompt="image"))

    assert len(client.models.calls) == 1


def test_fake_gemini_image_generator_returns_png_metadata() -> None:
    fake = FakeGeminiImageGenerator(png_bytes())

    result = fake.generate(GeminiImageGenerationRequest(prompt="test"))

    assert result.mime_type == "image/png"
    assert result.width == 1
    assert fake.requests[0].prompt == "test"
