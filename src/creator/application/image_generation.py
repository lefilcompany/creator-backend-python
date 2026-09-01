from __future__ import annotations

import hashlib
import json
from typing import Protocol, cast
from uuid import UUID

from creator.application.unit_of_work import UnitOfWork
from creator.config import Settings
from creator.domain.exceptions import ConflictError, EntityNotFoundError
from creator.prompts import (
    RenderedPrompt,
    build_advertising_image_prompt,
    generation_parameters_with_prompt_template,
)
from creator.repositories import ContentRecord, ImageGenerationStatusRecord, UserRecord


class GenerationQueue(Protocol):
    def enqueue(self, f: str, *args: object, job_id: str) -> object: ...


class IdempotencyConflictError(ConflictError):
    """Raised when an idempotency key is reused with a different request."""


class QueueEnqueueError(RuntimeError):
    """Raised when a Generation Job cannot be enqueued."""


def submit_image_generation(
    *,
    unit_of_work: UnitOfWork,
    queue: GenerationQueue,
    settings: Settings,
    user: UserRecord,
    content_id: UUID,
    style: str,
    idempotency_key: str,
) -> ImageGenerationStatusRecord:
    external_id = image_generation_external_id(user.id, idempotency_key)
    request_fingerprint = image_generation_request_fingerprint(
        content_id=content_id,
        style=style,
    )
    existing = unit_of_work.image_generations.get_status_by_external_id_for_user(
        user_id=user.id,
        external_id=external_id,
    )
    if existing is not None:
        _raise_for_idempotency_mismatch(existing, request_fingerprint)
        return existing

    content = unit_of_work.contents.get_by_id_for_user(user_id=user.id, content_id=content_id)
    if content is None:
        raise EntityNotFoundError("Content not found")

    rendered_prompt = build_image_generation_prompt(content=content, style=style)
    parameters = generation_parameters_with_prompt_template(
        {
            "style": style,
            "idempotency": {"request_fingerprint": request_fingerprint},
        },
        rendered_prompt,
    )
    generation_parameters = cast(dict[str, object], parameters)

    try:
        job = unit_of_work.image_generations.create_image_generation(
            workspace_id=content.workspace_id,
            content_id=content.id,
            requested_by_user_id=user.id,
            model=settings.gemini_image_model,
            prompt=rendered_prompt.text,
            parameters=generation_parameters,
            external_id=external_id,
        )
    except ConflictError:
        unit_of_work.rollback()
        existing = unit_of_work.image_generations.get_status_by_external_id_for_user(
            user_id=user.id,
            external_id=external_id,
        )
        if existing is None:
            raise
        _raise_for_idempotency_mismatch(existing, request_fingerprint)
        return existing

    try:
        queue.enqueue(
            "creator.workers.image_generation.run_image_generation",
            str(job.id),
            job_id=f"image-generation:{job.id}",
        )
    except Exception as error:
        unit_of_work.rollback()
        raise QueueEnqueueError("Image Generation Job could not be enqueued") from error

    unit_of_work.commit()
    return ImageGenerationStatusRecord(job=job, parameters=generation_parameters)


def build_image_generation_prompt(*, content: ContentRecord, style: str) -> RenderedPrompt:
    return build_advertising_image_prompt(
        context={
            "workspace_id": str(content.workspace_id),
            "content_type": content.content_type,
        },
        user_input={
            "content_id": str(content.id),
            "title": content.title,
            "content": content.payload,
            "style": style,
        },
    )


def image_generation_external_id(user_id: UUID, idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return f"image-generate:{user_id}:{digest}"


def image_generation_request_fingerprint(*, content_id: UUID, style: str) -> str:
    payload = json.dumps(
        {"content_id": str(content_id), "style": style},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _raise_for_idempotency_mismatch(
    status: ImageGenerationStatusRecord,
    request_fingerprint: str,
) -> None:
    idempotency = status.parameters.get("idempotency")
    if not isinstance(idempotency, dict):
        raise IdempotencyConflictError("Idempotency metadata is missing")
    if idempotency.get("request_fingerprint") != request_fingerprint:
        raise IdempotencyConflictError("Idempotency key was reused with a different request")
