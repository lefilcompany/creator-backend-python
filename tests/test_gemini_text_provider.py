from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors

from creator.config import Settings
from creator.integrations.gemini.exceptions import (
    GeminiBlockedContentError,
    GeminiInvalidResponseError,
    GeminiQuotaError,
    GeminiTimeoutError,
)
from creator.services.ai.gemini import GeminiLLMProvider

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


def provider(client: FakeClient, **settings_overrides: object) -> GeminiLLMProvider:
    return GeminiLLMProvider(
        Settings(gemini_api_key="secret", **settings_overrides),
        client=client,
        sleep=lambda delay: None,
        jitter=lambda delay: 0,
    )


def test_generate_text_success_uses_rendered_prompt_and_redacts_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = FakeClient([SimpleNamespace(text=" Generated launch copy ")])
    llm_provider = provider(client, gemini_text_model="gemini-text-test")

    result = llm_provider.generate_text(SENSITIVE_PROMPT, temperature=0.4)

    assert result == "Generated launch copy"
    assert client.models.calls[0]["model"] == "gemini-text-test"
    assert client.models.calls[0]["contents"] == SENSITIVE_PROMPT
    assert client.models.calls[0]["config"].temperature == 0.4
    assert SENSITIVE_PROMPT not in caplog.text
    assert "Generated launch copy" not in caplog.text
    assert "secret" not in caplog.text


def test_generate_text_collects_candidate_parts() -> None:
    response = SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(text="First paragraph"),
                        SimpleNamespace(text="Second paragraph"),
                    ]
                )
            )
        ]
    )
    llm_provider = provider(FakeClient([response]))

    assert llm_provider.generate_text("prompt") == "First paragraph\nSecond paragraph"


def test_generate_text_timeout_retries_until_success() -> None:
    sleeps: list[float] = []
    client = FakeClient([TimeoutError("slow"), SimpleNamespace(text="Recovered")])
    llm_provider = GeminiLLMProvider(
        Settings(gemini_api_key="secret", gemini_retry_attempts=2),
        client=client,
        sleep=sleeps.append,
        jitter=lambda delay: 0,
    )

    assert llm_provider.generate_text("prompt") == "Recovered"
    assert len(client.models.calls) == 2
    assert sleeps == [1.0]


def test_generate_text_timeout_raises_after_retry_limit() -> None:
    client = FakeClient([TimeoutError("slow"), TimeoutError("still slow")])
    llm_provider = provider(client, gemini_retry_attempts=2)

    with pytest.raises(GeminiTimeoutError):
        llm_provider.generate_text("prompt")

    assert len(client.models.calls) == 2


def test_generate_text_quota_error_is_retried_and_classified() -> None:
    llm_provider = provider(
        FakeClient([errors.APIError(429, {"error": {"message": "rate limit"}})]),
        gemini_retry_attempts=1,
    )

    with pytest.raises(GeminiQuotaError) as error:
        llm_provider.generate_text("prompt")

    assert error.value.retryable is True


def test_generate_text_blocked_content_does_not_retry() -> None:
    blocked_response = SimpleNamespace(
        prompt_feedback=SimpleNamespace(block_reason="SAFETY"),
        candidates=[],
    )
    client = FakeClient([blocked_response, SimpleNamespace(text="would not be used")])
    llm_provider = provider(client, gemini_retry_attempts=3)

    with pytest.raises(GeminiBlockedContentError):
        llm_provider.generate_text("prompt")

    assert len(client.models.calls) == 1


def test_generate_text_rejects_empty_response() -> None:
    llm_provider = provider(FakeClient([SimpleNamespace(text="  ", candidates=[])]))

    with pytest.raises(GeminiInvalidResponseError):
        llm_provider.generate_text("prompt")
