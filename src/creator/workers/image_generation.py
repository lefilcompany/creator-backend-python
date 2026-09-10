from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
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

logger = logging.getLogger(__name__)


def run_image_generation(job_id: str, request_id: str | None = None) -> None:
    try:
        parsed_job_id = UUID(job_id)
    except ValueError:
        return
    parsed_request_id = _safe_uuid(request_id)
    started_at = time.perf_counter()

    work_item = _claim_work_item(parsed_job_id)
    if work_item is None:
        return

    _log(
        "image_generation_started",
        request_id=parsed_request_id,
        job_id=parsed_job_id,
        attempt=work_item.job.attempt_count,
    )
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
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        _log(
            "image_generation_completed",
            request_id=parsed_request_id,
            job_id=parsed_job_id,
            attempt=work_item.job.attempt_count,
            duration_ms=duration_ms,
        )
    except StorageError:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        _log(
            "image_generation_failed",
            request_id=parsed_request_id,
            job_id=parsed_job_id,
            attempt=work_item.job.attempt_count,
            duration_ms=duration_ms,
            failure_code="STORAGE_UPLOAD_FAILED",
        )
        return
    except GeminiProviderError as error:
        failure_code = _provider_failure_code(error)
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        if error.retryable and work_item.job.attempt_count < work_item.job.max_attempts:
            _log(
                "image_generation_retryable_failure",
                request_id=parsed_request_id,
                job_id=parsed_job_id,
                attempt=work_item.job.attempt_count,
                duration_ms=duration_ms,
                failure_code=failure_code,
            )
            raise
        _fail_job(parsed_job_id, failure_code)
        _log(
            "image_generation_failed",
            request_id=parsed_request_id,
            job_id=parsed_job_id,
            attempt=work_item.job.attempt_count,
            duration_ms=duration_ms,
            failure_code=failure_code,
        )
    except Exception:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        if work_item.job.attempt_count < work_item.job.max_attempts:
            _log(
                "image_generation_retryable_failure",
                request_id=parsed_request_id,
                job_id=parsed_job_id,
                attempt=work_item.job.attempt_count,
                duration_ms=duration_ms,
                failure_code="IMAGE_GENERATION_FAILED",
            )
            raise
        _fail_job(parsed_job_id, "IMAGE_GENERATION_FAILED")
        _log(
            "image_generation_failed",
            request_id=parsed_request_id,
            job_id=parsed_job_id,
            attempt=work_item.job.attempt_count,
            duration_ms=duration_ms,
            failure_code="IMAGE_GENERATION_FAILED",
        )
        raise


def recover_stale_processing_jobs() -> int:
    settings = get_settings()
    older_than = datetime.now(UTC) - timedelta(
        seconds=settings.image_generation_stale_processing_seconds
    )
    with SqlAlchemyUnitOfWork() as unit_of_work:
        recovered = unit_of_work.image_generations.fail_stale_processing(
            older_than=older_than,
            failure_code="IMAGE_GENERATION_STALE_PROCESSING",
            failure_message="Image generation did not finish before the processing timeout",
        )
        unit_of_work.commit()
        if recovered:
            logger.warning(
                "image_generation_stale_jobs_failed",
                extra={"recovered_count": recovered},
            )
        return recovered


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


def _safe_uuid(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _log(
    event: str,
    *,
    request_id: UUID | None,
    job_id: UUID,
    attempt: int,
    duration_ms: int | None = None,
    failure_code: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "request_id": str(request_id) if request_id else None,
        "generation_job_id": str(job_id),
        "attempt": attempt,
    }
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    if failure_code is not None:
        payload["failure_code"] = failure_code
    if failure_code is None and event.endswith("completed"):
        logger.info(event, extra=payload)
    elif event.endswith("started"):
        logger.info(event, extra=payload)
    else:
        logger.warning(event, extra=payload)
