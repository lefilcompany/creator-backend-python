from __future__ import annotations

from typing import Protocol

from creator.config import Settings
from creator.integrations.gemini.image_generator import (
    GeminiImageGenerationRequest,
    GeminiImageGenerationResult,
    GeminiImageGenerator,
)


class ImageGenerator(Protocol):
    def generate(self, request: GeminiImageGenerationRequest) -> GeminiImageGenerationResult: ...


def create_image_generator(settings: Settings) -> ImageGenerator:
    return GeminiImageGenerator(settings)
