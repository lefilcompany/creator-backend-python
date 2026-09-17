from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ImageReviewRequest:
    image_bytes: bytes
    mime_type: str
    prompt: str
    briefing: str
    brand_context: Mapping[str, object]
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ImageReviewResult:
    decision: str
    score: float
    feedback: tuple[str, ...] = ()
    safety_issues: tuple[str, ...] = ()
    provider: str = "unknown"
    model: str | None = None


class MultimodalImageReviewer(Protocol):
    def review(self, request: ImageReviewRequest) -> ImageReviewResult: ...


class UnconfiguredMultimodalImageReviewer:
    def review(self, request: ImageReviewRequest) -> ImageReviewResult:
        raise RuntimeError("Multimodal image reviewer is not configured")
