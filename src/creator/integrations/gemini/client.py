from __future__ import annotations

from typing import Any

from google import genai
from google.genai import types

from creator.config import Settings
from creator.integrations.gemini.exceptions import GeminiAuthenticationError


def create_gemini_client(settings: Settings) -> Any:
    if not settings.gemini_api_key:
        raise GeminiAuthenticationError("GEMINI_API_KEY is required")

    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(
            timeout=settings.gemini_timeout_seconds * 1000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
