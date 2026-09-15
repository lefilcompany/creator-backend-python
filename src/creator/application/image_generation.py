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

MAX_GENERATION_PROMPT_LENGTH = 20_000


class GenerationQueue(Protocol):
    def enqueue_image_generation(self, *, job_id: UUID, request_id: UUID) -> object: ...


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
    style: str | None,
    idempotency_key: str,
    request_id: UUID,
) -> ImageGenerationStatusRecord:
    stored_settings = unit_of_work.settings.get_by_user_id(user.id)
    resolved_style = style or (stored_settings.visual_style if stored_settings else "photographic")
    external_id = image_generation_external_id(user.id, idempotency_key)
    request_fingerprint = image_generation_request_fingerprint(
        content_id=content_id,
        style=resolved_style,
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

    rendered_prompt = build_image_generation_prompt(
        content=content,
        style=resolved_style,
        settings_context={
            "brand_name": stored_settings.brand_name,
            "segment": stored_settings.segment,
            "tone": stored_settings.tone,
            "voice": stored_settings.voice,
            "visual_style": stored_settings.visual_style,
            "default_preferences": stored_settings.default_preferences,
        }
        if stored_settings
        else {},
    )
    parameters = generation_parameters_with_prompt_template(
        {
            "style": resolved_style,
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
            max_attempts=settings.image_generation_job_max_attempts,
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
        queue.enqueue_image_generation(job_id=job.id, request_id=request_id)
    except Exception as error:
        unit_of_work.rollback()
        raise QueueEnqueueError("Image Generation Job could not be enqueued") from error

    unit_of_work.commit()
    return ImageGenerationStatusRecord(job=job, parameters=generation_parameters)


def submit_image_regeneration(
    *,
    unit_of_work: UnitOfWork,
    queue: GenerationQueue,
    settings: Settings,
    user: UserRecord,
    image_id: UUID,
    style: str | None,
    idempotency_key: str,
    request_id: UUID,
) -> ImageGenerationStatusRecord:
    original_image = unit_of_work.image_generations.get_image_for_user(
        user_id=user.id,
        image_id=image_id,
    )
    if original_image is None:
        raise EntityNotFoundError("Image not found")

    stored_settings = unit_of_work.settings.get_by_user_id(user.id)
    resolved_style = (
        style
        or _style_from_metadata(original_image.metadata)
        or (stored_settings.visual_style if stored_settings else "photographic")
    )
    external_id = image_regeneration_external_id(user.id, idempotency_key)
    request_fingerprint = image_regeneration_request_fingerprint(
        image_id=image_id,
        style=resolved_style,
    )
    existing = unit_of_work.image_generations.get_status_by_external_id_for_user(
        user_id=user.id,
        external_id=external_id,
    )
    if existing is not None:
        _raise_for_idempotency_mismatch(existing, request_fingerprint)
        return existing

    regeneration_prompt = build_image_regeneration_prompt(
        original_prompt=original_image.prompt,
        style=resolved_style,
    )
    parameters = generation_parameters_with_prompt_template(
        {
            "style": resolved_style,
            "regenerated_from_image_id": str(original_image.id),
            "regenerated_from_generation_id": str(original_image.generation_id),
            "regenerated_from_version_number": original_image.version_number,
            "regenerated_from_model": original_image.model,
            "regenerated_from_prompt_sha256": hashlib.sha256(
                original_image.prompt.encode("utf-8")
            ).hexdigest(),
            "idempotency": {"request_fingerprint": request_fingerprint},
        },
        regeneration_prompt,
    )
    generation_parameters = cast(dict[str, object], parameters)

    try:
        job = unit_of_work.image_generations.create_image_generation(
            workspace_id=original_image.workspace_id,
            content_id=original_image.content_id,
            requested_by_user_id=user.id,
            model=original_image.model or settings.gemini_image_model,
            prompt=regeneration_prompt.text,
            parameters=generation_parameters,
            external_id=external_id,
            max_attempts=settings.image_generation_job_max_attempts,
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
        queue.enqueue_image_generation(job_id=job.id, request_id=request_id)
    except Exception as error:
        unit_of_work.rollback()
        raise QueueEnqueueError("Image Generation Job could not be enqueued") from error

    unit_of_work.commit()
    return ImageGenerationStatusRecord(job=job, parameters=generation_parameters)


def build_image_generation_prompt(
    *,
    content: ContentRecord,
    style: str,
    settings_context: dict[str, object] | None = None,
) -> RenderedPrompt:
    return build_advertising_image_prompt(
        context={
            "workspace_id": str(content.workspace_id),
            "content_type": content.content_type,
            "settings": settings_context or {},
        },
        user_input={
            "content_id": str(content.id),
            "title": content.title,
            "content": content.payload,
            "style": style,
        },
    )


def build_image_regeneration_prompt(*, original_prompt: str, style: str) -> RenderedPrompt:
    prompt = _render_image_regeneration_prompt(original_prompt=original_prompt, style=style)
    while len(prompt.text) > MAX_GENERATION_PROMPT_LENGTH and len(original_prompt) > 1:
        overflow = len(prompt.text) - MAX_GENERATION_PROMPT_LENGTH
        original_prompt = original_prompt[: max(1, len(original_prompt) - overflow - 256)]
        prompt = _render_image_regeneration_prompt(
            original_prompt=f"{original_prompt}\n[truncated to fit Generation prompt limit]",
            style=style,
        )
    return prompt


def _render_image_regeneration_prompt(*, original_prompt: str, style: str) -> RenderedPrompt:
    return build_advertising_image_prompt(
        context={
            "operation": "image_regeneration",
            "source": "original_image_prompt",
            "preserve_original_content_context": True,
        },
        user_input={
            "style": style,
            "instruction": (
                "Regenerate a new image version from the original prompt below. "
                "Preserve the original content, business context, composition intent, and "
                "constraints. Apply only the requested style change when it differs from "
                "the original."
            ),
            "original_prompt": original_prompt,
        },
        metadata={"regeneration": True},
    )


def image_generation_external_id(user_id: UUID, idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return f"image-generate:{user_id}:{digest}"


def image_regeneration_external_id(user_id: UUID, idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return f"image-regenerate:{user_id}:{digest}"


def image_generation_request_fingerprint(*, content_id: UUID, style: str) -> str:
    payload = json.dumps(
        {"content_id": str(content_id), "style": style},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def image_regeneration_request_fingerprint(*, image_id: UUID, style: str) -> str:
    payload = json.dumps(
        {"image_id": str(image_id), "style": style},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _style_from_metadata(metadata: dict[str, object]) -> str | None:
    style = metadata.get("style")
    return style if isinstance(style, str) else None


def _raise_for_idempotency_mismatch(
    status: ImageGenerationStatusRecord,
    request_fingerprint: str,
) -> None:
    idempotency = status.parameters.get("idempotency")
    if not isinstance(idempotency, dict):
        raise IdempotencyConflictError("Idempotency metadata is missing")
    if idempotency.get("request_fingerprint") != request_fingerprint:
        raise IdempotencyConflictError("Idempotency key was reused with a different request")
