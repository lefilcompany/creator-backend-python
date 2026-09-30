from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class GenerationJobStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class GenerationArtifactType(StrEnum):
    IMAGE = "IMAGE"
    COPY = "COPY"
    CAPTION = "CAPTION"


class GenerationOperation(StrEnum):
    CREATE = "CREATE"
    REGENERATE = "REGENERATE"
    TRANSFORM = "TRANSFORM"


@dataclass(frozen=True, slots=True)
class TextGenerationInput:
    prompt: str
    language: str = "pt-BR"
    max_characters: int = 2000

    def __post_init__(self) -> None:
        if not 1 <= len(self.prompt) <= 20_000:
            raise ValueError("prompt must contain between 1 and 20000 characters")
        if not 1 <= self.max_characters <= 20_000:
            raise ValueError("max_characters must be between 1 and 20000")


@dataclass(frozen=True, slots=True)
class ImageGenerationInput:
    prompt: str
    mime_type: str = "image/png"
    width: int = 1024
    height: int = 1024

    def __post_init__(self) -> None:
        if not 1 <= len(self.prompt) <= 20_000:
            raise ValueError("prompt must contain between 1 and 20000 characters")
        if self.mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise ValueError("unsupported image mime_type")
        if not 1 <= self.width <= 8192 or not 1 <= self.height <= 8192:
            raise ValueError("image dimensions must be between 1 and 8192")


@dataclass(frozen=True, slots=True)
class TextGenerationOutput:
    text: str
    character_count: int
    language: str
    content_version: int

    def __post_init__(self) -> None:
        if not 1 <= len(self.text) <= 20_000 or self.character_count != len(self.text):
            raise ValueError("text output length metadata is invalid")
        if self.content_version < 1:
            raise ValueError("content_version must be positive")


@dataclass(frozen=True, slots=True)
class ImageGenerationOutput:
    storage_path: str
    mime_type: str
    byte_size: int
    width: int
    height: int
    content_version: int

    def __post_init__(self) -> None:
        if not self.storage_path or self.mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise ValueError("image output must reference a supported stored object")
        if self.byte_size < 1 or self.width < 1 or self.height < 1 or self.content_version < 1:
            raise ValueError("image output metadata is invalid")


@dataclass(frozen=True, slots=True)
class GenerationPolicy:
    max_attempts: int = 1
    timeout_seconds: int = 300
    idempotency_key: str | None = None
    failure_policy: str = "FAIL"

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.timeout_seconds < 1:
            raise ValueError("retry and timeout limits must be positive")
        if self.failure_policy not in {"FAIL", "RETRY", "PARTIAL"}:
            raise ValueError("unsupported failure policy")


@dataclass(frozen=True, slots=True)
class SanitizedGenerationResult:
    artifact_type: GenerationArtifactType
    version: int
    correlation_id: str
    result: dict[str, Any]


ALLOWED_TRANSITIONS: dict[GenerationJobStatus, frozenset[GenerationJobStatus]] = {
    GenerationJobStatus.PENDING: frozenset(
        {GenerationJobStatus.PROCESSING, GenerationJobStatus.FAILED}
    ),
    GenerationJobStatus.PROCESSING: frozenset(
        {GenerationJobStatus.COMPLETED, GenerationJobStatus.FAILED}
    ),
    GenerationJobStatus.COMPLETED: frozenset(),
    GenerationJobStatus.FAILED: frozenset(),
}


def can_transition(current: GenerationJobStatus, target: GenerationJobStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]
