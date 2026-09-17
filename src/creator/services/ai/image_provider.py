from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from creator.config import Settings


@dataclass(frozen=True, slots=True)
class ImageGenerationRequest:
    prompt: str
    model: str | None = None
    output_mime_type: str = "image/png"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ImageGenerationResult:
    image_bytes: bytes
    mime_type: str
    width: int
    height: int
    model: str
    prompt: str
    metadata: dict[str, object]


class ImageGenerator(Protocol):
    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...


def create_image_generator(settings: Settings) -> ImageGenerator:
    from creator.integrations.gemini.image_generator import GeminiImageGenerator

    return GeminiImageGenerator(settings)
