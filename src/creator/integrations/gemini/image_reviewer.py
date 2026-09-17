from __future__ import annotations

import json
from typing import Any

from google.genai import types

from creator.config import Settings
from creator.integrations.gemini.client import create_gemini_client
from creator.integrations.gemini.exceptions import GeminiInvalidResponseError
from creator.services.ai.reviewer import ImageReviewRequest, ImageReviewResult


class GeminiMultimodalImageReviewer:
    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client if client is not None else create_gemini_client(settings)

    def review(self, request: ImageReviewRequest) -> ImageReviewResult:
        prompt = (
            "Review the supplied marketing image against the briefing and brand context. "
            "Return JSON only with decision (APPROVED, REFINE, or REJECTED), score, "
            "feedback (array), and safety_issues (array). "
            f"Briefing: {request.briefing}\nBrand context: {dict(request.brand_context)}\n"
            f"Image prompt: {request.prompt}"
        )
        response = self._client.models.generate_content(
            model=self._settings.agent_reviewer_model,
            contents=[
                prompt,
                types.Part.from_bytes(data=request.image_bytes, mime_type=request.mime_type),
            ],
            config=types.GenerateContentConfig(temperature=0),
        )
        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise GeminiInvalidResponseError("Gemini image reviewer returned no text")
        try:
            payload = json.loads(_strip_json_fence(text))
            return ImageReviewResult(
                decision=str(payload["decision"]),
                score=float(payload["score"]),
                feedback=tuple(str(item) for item in payload.get("feedback", [])),
                safety_issues=tuple(str(item) for item in payload.get("safety_issues", [])),
                provider="gemini",
                model=self._settings.agent_reviewer_model,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise GeminiInvalidResponseError(
                "Gemini image reviewer returned invalid JSON"
            ) from error


def _strip_json_fence(text: str) -> str:
    normalized = text.strip()
    if normalized.startswith("```"):
        normalized = normalized.split("\n", 1)[-1]
        if normalized.endswith("```"):
            normalized = normalized[:-3]
    return normalized.strip()
