from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from creator.config import Settings
from creator.domain.generation import GenerationJobStatus
from creator.integrations.gemini.exceptions import GeminiBlockedContentError, GeminiTimeoutError
from creator.integrations.gemini.image_generator import (
    GeminiImageGenerationRequest,
    GeminiImageGenerationResult,
)
from creator.repositories import GenerationJobRecord, ImageGenerationWorkItem, UserRecord
from creator.workers import image_generation

NOW = datetime(2026, 9, 1, tzinfo=UTC)


class FakeImageGenerator:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.requests: list[GeminiImageGenerationRequest] = []

    def generate(self, request: GeminiImageGenerationRequest) -> GeminiImageGenerationResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return GeminiImageGenerationResult(
            image_bytes=b"image-bytes",
            mime_type="image/png",
            width=2,
            height=3,
            model=request.model or "gemini-image",
            prompt=request.prompt,
            metadata={"provider": "gemini"},
        )


class FakeStorage:
    pass


class FakeImageGenerationRepository:
    def __init__(self, work_item: ImageGenerationWorkItem | None = None) -> None:
        self.work_item = work_item
        self.failed: list[dict[str, object]] = []
        self.stale_calls: list[dict[str, object]] = []

    def claim_pending_by_id(self, job_id: UUID) -> ImageGenerationWorkItem | None:
        return self.work_item

    def fail_job(
        self,
        job_id: UUID,
        *,
        failure_code: str,
        failure_message: str,
    ) -> GenerationJobRecord:
        self.failed.append(
            {
                "job_id": job_id,
                "failure_code": failure_code,
                "failure_message": failure_message,
            }
        )
        assert self.work_item is not None
        return self.work_item.job

    def fail_stale_processing(
        self,
        *,
        older_than: datetime,
        failure_code: str,
        failure_message: str,
    ) -> int:
        self.stale_calls.append(
            {
                "older_than": older_than,
                "failure_code": failure_code,
                "failure_message": failure_message,
            }
        )
        return 2


class FakeUnitOfWork:
    def __init__(self, repository: FakeImageGenerationRepository) -> None:
        self.image_generations = repository
        self.commits = 0

    def __enter__(self) -> FakeUnitOfWork:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        return None


def job_record(*, attempt_count: int = 1, max_attempts: int = 3) -> GenerationJobRecord:
    return GenerationJobRecord(
        id=UUID("50000000-0000-0000-0000-000000000001"),
        workspace_id=uuid4(),
        generation_id=uuid4(),
        content_id=uuid4(),
        status=GenerationJobStatus.PROCESSING,
        external_id=None,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        failure_code=None,
        failure_message=None,
        queued_at=NOW,
        started_at=NOW,
        completed_at=None,
        failed_at=None,
        created_at=NOW,
        updated_at=NOW,
        deleted_at=None,
    )


def user_record() -> UserRecord:
    return UserRecord(
        id=uuid4(),
        external_id="principal-123",
        email="principal@example.com",
        display_name="Principal Example",
        global_role="membro",
        created_at=NOW,
        updated_at=NOW,
        deleted_at=None,
    )


def work_item(*, attempt_count: int = 1, max_attempts: int = 3) -> ImageGenerationWorkItem:
    return ImageGenerationWorkItem(
        job=job_record(attempt_count=attempt_count, max_attempts=max_attempts),
        model="gemini-image",
        prompt="Generate",
        parameters={"style": "photographic"},
        requested_by_user=user_record(),
    )


def patch_worker(
    monkeypatch: pytest.MonkeyPatch,
    *,
    repository: FakeImageGenerationRepository,
    generator: FakeImageGenerator,
    persisted: list[object] | None = None,
) -> None:
    monkeypatch.setattr(image_generation, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(
        image_generation,
        "SqlAlchemyUnitOfWork",
        lambda: FakeUnitOfWork(repository),
    )
    monkeypatch.setattr(image_generation, "create_image_generator", lambda settings: generator)
    monkeypatch.setattr(image_generation, "create_storage_provider", lambda settings: FakeStorage())

    def fake_persist_generated_image(**kwargs: object) -> object:
        if persisted is not None:
            persisted.append(kwargs)
        return object()

    monkeypatch.setattr(image_generation, "persist_generated_image", fake_persist_generated_image)


def test_run_image_generation_completes_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    persisted: list[object] = []
    repository = FakeImageGenerationRepository(work_item())
    generator = FakeImageGenerator()
    patch_worker(monkeypatch, repository=repository, generator=generator, persisted=persisted)

    image_generation.run_image_generation(
        "50000000-0000-0000-0000-000000000001",
        "70000000-0000-0000-0000-000000000001",
    )

    assert len(generator.requests) == 1
    assert persisted
    assert repository.failed == []


def test_run_image_generation_raises_retryable_failure_before_last_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeImageGenerationRepository(work_item(attempt_count=1, max_attempts=3))
    generator = FakeImageGenerator(error=GeminiTimeoutError("slow", retryable=True))
    patch_worker(monkeypatch, repository=repository, generator=generator)

    with pytest.raises(GeminiTimeoutError):
        image_generation.run_image_generation("50000000-0000-0000-0000-000000000001")

    assert repository.failed == []


def test_run_image_generation_marks_final_retryable_failure_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeImageGenerationRepository(work_item(attempt_count=3, max_attempts=3))
    generator = FakeImageGenerator(error=GeminiTimeoutError("slow", retryable=True))
    patch_worker(monkeypatch, repository=repository, generator=generator)

    image_generation.run_image_generation("50000000-0000-0000-0000-000000000001")

    assert repository.failed[0]["failure_code"] == "PROVIDER_TIMEOUT"


def test_run_image_generation_marks_permanent_failure_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeImageGenerationRepository(work_item(attempt_count=1, max_attempts=3))
    generator = FakeImageGenerator(error=GeminiBlockedContentError("blocked"))
    patch_worker(monkeypatch, repository=repository, generator=generator)

    image_generation.run_image_generation("50000000-0000-0000-0000-000000000001")

    assert repository.failed[0]["failure_code"] == "PROVIDER_CONTENT_BLOCKED"


def test_recover_stale_processing_jobs_marks_old_jobs_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = FakeImageGenerationRepository()
    patch_worker(monkeypatch, repository=repository, generator=FakeImageGenerator())

    recovered = image_generation.recover_stale_processing_jobs()

    assert recovered == 2
    assert repository.stale_calls[0]["failure_code"] == "IMAGE_GENERATION_STALE_PROCESSING"
