from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

SUPPORTED_STORAGE_MIME_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})


class StorageError(RuntimeError):
    """Base class for object storage failures."""


class StorageConfigurationError(StorageError):
    """Raised when storage settings are incomplete."""


class StorageValidationError(StorageError):
    """Raised when an object cannot be safely stored."""


class StorageUploadError(StorageError):
    """Raised when upload fails before persistence is complete."""


class StorageDeleteError(StorageError):
    """Raised when object cleanup fails."""


class StorageUrlError(StorageError):
    """Raised when a usable object URL cannot be generated."""


@dataclass(frozen=True, slots=True)
class UploadObjectRequest:
    path: str
    content: bytes
    mime_type: str
    checksum_sha256: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StoredObject:
    path: str
    url: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    metadata: dict[str, object] = field(default_factory=dict)


class StorageProvider(Protocol):
    def upload(self, request: UploadObjectRequest) -> StoredObject:
        """Store content and return a provider-neutral object reference."""

    def delete(self, path: str) -> None:
        """Delete content at a provider path."""

    def get_url(self, path: str) -> str:
        """Return a usable URL for a stored object."""


def image_extension_for_mime_type(mime_type: str) -> str:
    extensions = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
    }
    try:
        return extensions[mime_type]
    except KeyError as error:
        raise StorageValidationError("Unsupported image MIME type") from error


def immutable_image_path(
    *,
    user_external_id: str,
    content_id: object,
    version_number: int,
    mime_type: str,
) -> str:
    if version_number < 1:
        raise StorageValidationError("Image version must be positive")
    safe_user = _safe_path_segment(user_external_id)
    extension = image_extension_for_mime_type(mime_type)
    return f"users/{safe_user}/contents/{content_id}/versions/{version_number}/image.{extension}"


def _safe_path_segment(value: str) -> str:
    normalized = value.strip()
    if not normalized or "/" in normalized or "\\" in normalized or normalized in {".", ".."}:
        raise StorageValidationError("Invalid storage path segment")
    return normalized
