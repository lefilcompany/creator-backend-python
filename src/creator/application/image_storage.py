from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from creator.application.unit_of_work import UnitOfWork
from creator.repositories import GenerationJobRecord, ImageMetadata, ImageRecord, UserRecord
from creator.services.storage.provider import (
    StorageError,
    StorageObjectNotFoundError,
    StorageProvider,
    StorageValidationError,
    StoredObject,
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
    existing = unit_of_work.image_generations.get_image_by_generation_id(job.generation_id)
    if existing is not None:
        return existing

    version_number = unit_of_work.image_generations.reserve_image_version(job.id)
    storage_path = immutable_image_path(
        user_external_id=user.external_id,
        content_id=job.content_id,
        version_number=version_number,
        mime_type=image.mime_type,
    )
    checksum_sha256 = hashlib.sha256(image.content).hexdigest()
    validate_image_integrity(image)
    upload_request = UploadObjectRequest(
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

    try:
        stored_object = storage.upload(upload_request)
        uploaded_now = True
    except StorageError:
        stored_object = _recover_existing_upload(
            storage=storage,
            request=upload_request,
            checksum_sha256=checksum_sha256,
        )
        if stored_object is None:
            unit_of_work.image_generations.fail_job(
                job.id,
                failure_code="STORAGE_UPLOAD_FAILED",
                failure_message="Generated image could not be persisted",
            )
            unit_of_work.commit()
            raise
        uploaded_now = False

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
        if uploaded_now:
            storage.delete(stored_object.path)
        raise


def validate_image_integrity(image: GeneratedImage) -> None:
    if image.width <= 0 or image.height <= 0:
        raise StorageValidationError("Generated image dimensions are invalid")


def _recover_existing_upload(
    *,
    storage: StorageProvider,
    request: UploadObjectRequest,
    checksum_sha256: str,
) -> StoredObject | None:
    try:
        metadata = storage.stat(request.path)
    except StorageObjectNotFoundError:
        return None
    except StorageError:
        return None
    if metadata.checksum_sha256 and metadata.checksum_sha256 != checksum_sha256:
        return None
    if metadata.mime_type != request.mime_type:
        return None
    try:
        url = storage.get_url(request.path)
    except StorageError:
        return None
    return StoredObject(
        path=request.path,
        url=url,
        mime_type=request.mime_type,
        size_bytes=metadata.size_bytes or len(request.content),
        checksum_sha256=metadata.checksum_sha256 or checksum_sha256,
        metadata={**metadata.metadata, **request.metadata},
    )
