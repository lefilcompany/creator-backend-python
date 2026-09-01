from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from creator.application.unit_of_work import UnitOfWork
from creator.repositories import GenerationJobRecord, ImageMetadata, ImageRecord, UserRecord
from creator.services.storage.provider import (
    StorageError,
    StorageProvider,
    StorageValidationError,
    UploadObjectRequest,
    immutable_image_path,
)


@dataclass(frozen=True, slots=True)
class GeneratedImage:
    content: bytes
    mime_type: str
    width: int
    height: int
    model: str
    prompt: str
    metadata: dict[str, object] = field(default_factory=dict)


def persist_generated_image(
    *,
    unit_of_work: UnitOfWork,
    storage: StorageProvider,
    job: GenerationJobRecord,
    user: UserRecord,
    image: GeneratedImage,
) -> ImageRecord:
    version_number = unit_of_work.image_generations.next_image_version(job.content_id)
    storage_path = immutable_image_path(
        user_external_id=user.external_id,
        content_id=job.content_id,
        version_number=version_number,
        mime_type=image.mime_type,
    )
    checksum_sha256 = hashlib.sha256(image.content).hexdigest()

    try:
        validate_image_integrity(image)
        stored_object = storage.upload(
            UploadObjectRequest(
                path=storage_path,
                content=image.content,
                mime_type=image.mime_type,
                checksum_sha256=checksum_sha256,
                metadata={
                    "workspace_id": str(job.workspace_id),
                    "content_id": str(job.content_id),
                    "generation_id": str(job.generation_id),
                    "version_number": version_number,
                    "owner_external_id": user.external_id,
                    **image.metadata,
                },
            )
        )
    except StorageError:
        unit_of_work.image_generations.fail_job(
            job.id,
            failure_code="STORAGE_UPLOAD_FAILED",
            failure_message="Generated image could not be persisted",
        )
        unit_of_work.commit()
        raise

    try:
        completed = unit_of_work.image_generations.complete_job(
            job.id,
            ImageMetadata(
                storage_path=stored_object.path,
                public_url=stored_object.url,
                mime_type=stored_object.mime_type,
                width=image.width,
                height=image.height,
                model=image.model,
                prompt=image.prompt,
                version_number=version_number,
                metadata={
                    **image.metadata,
                    "storage_provider": stored_object.metadata.get("provider"),
                    "storage_size_bytes": stored_object.size_bytes,
                    "storage_checksum_sha256": stored_object.checksum_sha256,
                    "storage_url_expires": True,
                },
            ),
        )
        unit_of_work.commit()
        return completed
    except Exception:
        storage.delete(stored_object.path)
        raise


def validate_image_integrity(image: GeneratedImage) -> None:
    if image.width <= 0 or image.height <= 0:
        raise StorageValidationError("Generated image dimensions are invalid")
