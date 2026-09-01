from __future__ import annotations

from uuid import UUID

from creator.application.image_storage import GeneratedImage, persist_generated_image
from creator.config import get_settings
from creator.domain.exceptions import InvalidStateTransitionError
from creator.infrastructure.storage import create_storage_provider
from creator.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from creator.integrations.gemini.exceptions import (
    GeminiAuthenticationError,
    GeminiBlockedContentError,
    GeminiInvalidResponseError,
    GeminiProviderError,
    GeminiQuotaError,
    GeminiTimeoutError,
    GeminiTransientError,
)
from creator.integrations.gemini.image_generator import GeminiImageGenerationRequest
from creator.repositories import ImageGenerationWorkItem, JsonObject
from creator.services.ai.image_provider import create_image_generator
from creator.services.storage.provider import StorageError


def run_image_generation(job_id: str) -> None:
    try:
        parsed_job_id = UUID(job_id)
    except ValueError:
        return

    work_item = _claim_work_item(parsed_job_id)
    if work_item is None:
        return

    settings = get_settings()
    try:
        result = create_image_generator(settings).generate(
            GeminiImageGenerationRequest(
                prompt=work_item.prompt,
                model=work_item.model,
                metadata=_image_request_metadata(work_item),
            )
        )
        with SqlAlchemyUnitOfWork() as unit_of_work:
            persist_generated_image(
                unit_of_work=unit_of_work,
                storage=create_storage_provider(settings),
                job=work_item.job,
                user=work_item.requested_by_user,
                image=GeneratedImage(
                    content=result.image_bytes,
                    mime_type=result.mime_type,
                    width=result.width,
                    height=result.height,
                    model=result.model,
                    prompt=result.prompt,
                    metadata=result.metadata,
                ),
            )
    except StorageError:
        return
    except GeminiProviderError as error:
        _fail_job(parsed_job_id, _provider_failure_code(error))
    except Exception:
        _fail_job(parsed_job_id, "IMAGE_GENERATION_FAILED")
        raise


def _claim_work_item(job_id: UUID) -> ImageGenerationWorkItem | None:
    with SqlAlchemyUnitOfWork() as unit_of_work:
        work_item = unit_of_work.image_generations.claim_pending_by_id(job_id)
        if work_item is None:
            return None
        unit_of_work.commit()
        return work_item


def _fail_job(job_id: UUID, failure_code: str) -> None:
    with SqlAlchemyUnitOfWork() as unit_of_work:
        try:
            unit_of_work.image_generations.fail_job(
                job_id,
                failure_code=failure_code,
                failure_message="Image generation failed",
            )
        except InvalidStateTransitionError:
            return
        unit_of_work.commit()


def _image_request_metadata(work_item: ImageGenerationWorkItem) -> JsonObject:
    metadata: JsonObject = {}
    style = work_item.parameters.get("style")
    if isinstance(style, str):
        metadata["style"] = style

    prompt_template = work_item.parameters.get("prompt_template")
    if isinstance(prompt_template, dict):
        template_id = prompt_template.get("id")
        template_version = prompt_template.get("version")
        input_hash = prompt_template.get("input_hash")
        if isinstance(template_id, str):
            metadata["prompt_template_id"] = template_id
        if isinstance(template_version, str):
            metadata["prompt_template_version"] = template_version
        if isinstance(input_hash, str):
            metadata["prompt_input_hash"] = input_hash
    return metadata


def _provider_failure_code(error: GeminiProviderError) -> str:
    if isinstance(error, GeminiAuthenticationError):
        return "PROVIDER_AUTHENTICATION_FAILED"
    if isinstance(error, GeminiQuotaError):
        return "PROVIDER_QUOTA_EXCEEDED"
    if isinstance(error, GeminiTimeoutError):
        return "PROVIDER_TIMEOUT"
    if isinstance(error, GeminiBlockedContentError):
        return "PROVIDER_CONTENT_BLOCKED"
    if isinstance(error, GeminiInvalidResponseError):
        return "PROVIDER_INVALID_RESPONSE"
    if isinstance(error, GeminiTransientError):
        return "PROVIDER_TRANSIENT_FAILED"
    return "PROVIDER_FAILED"
