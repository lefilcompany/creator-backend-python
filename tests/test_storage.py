from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from creator.application.image_storage import GeneratedImage, persist_generated_image
from creator.config import Settings
from creator.domain.generation import GenerationJobStatus
from creator.infrastructure.storage import LocalStorageProvider, SupabaseStorageProvider
from creator.repositories import GenerationJobRecord, ImageMetadata, ImageRecord, UserRecord
from creator.services.storage.provider import (
    StorageUploadError,
    StorageUrlError,
    StorageValidationError,
    StoredObject,
    UploadObjectRequest,
    immutable_image_path,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)


class FakeStorageResponse:
    def __init__(self, payload: bytes = b"{}", status: int = 200) -> None:
        self.status = status
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class FakeStorageOpener:
    def __init__(self, responses: list[FakeStorageResponse]) -> None:
        self.responses = responses
        self.requests: list[object] = []
        self.timeouts: list[float] = []

    def __call__(self, request: object, timeout: float) -> FakeStorageResponse:
        self.requests.append(request)
        self.timeouts.append(timeout)
        return self.responses.pop(0)


class FakeStorage:
    def __init__(self, *, fail_upload: bool = False) -> None:
        self.fail_upload = fail_upload
        self.uploads: list[UploadObjectRequest] = []
        self.deleted: list[str] = []

    def upload(self, request: UploadObjectRequest) -> StoredObject:
        self.uploads.append(request)
        if self.fail_upload:
            raise StorageUploadError("upload failed")
        return StoredObject(
            path=request.path,
            url=f"https://storage.example/{request.path}",
            mime_type=request.mime_type,
            size_bytes=len(request.content),
            checksum_sha256=request.checksum_sha256 or "checksum",
            metadata={"provider": "fake"},
        )

    def delete(self, path: str) -> None:
        self.deleted.append(path)

    def get_url(self, path: str) -> str:
        return f"https://storage.example/{path}"


class FakeImageGenerationRepository:
    def __init__(self, *, complete_error: Exception | None = None) -> None:
        self.complete_error = complete_error
        self.failed: list[dict[str, object]] = []
        self.completed: list[ImageMetadata] = []

    def create_image_generation(self, **kwargs: object) -> GenerationJobRecord:
        raise NotImplementedError

    def get_job_for_user(self, **kwargs: object) -> GenerationJobRecord | None:
        raise NotImplementedError

    def list_history_for_user(self, **kwargs: object) -> object:
        raise NotImplementedError

    def claim_next_pending(self, **kwargs: object) -> GenerationJobRecord | None:
        raise NotImplementedError

    def next_image_version(self, content_id: UUID) -> int:
        return 3

    def complete_job(self, job_id: UUID, image: ImageMetadata) -> ImageRecord:
        self.completed.append(image)
        if self.complete_error is not None:
            raise self.complete_error
        return ImageRecord(
            id=uuid4(),
            workspace_id=uuid4(),
            content_id=uuid4(),
            generation_id=uuid4(),
            version_number=3,
            storage_path=image.storage_path,
            public_url=image.public_url,
            mime_type=image.mime_type,
            width=image.width,
            height=image.height,
            model=image.model,
            prompt=image.prompt,
            metadata=image.metadata,
            created_at=NOW,
            updated_at=NOW,
            deleted_at=None,
        )

    def fail_job(self, job_id: UUID, *, failure_code: str, failure_message: str) -> object:
        self.failed.append(
            {
                "job_id": job_id,
                "failure_code": failure_code,
                "failure_message": failure_message,
            }
        )
        return object()


class FakeUnitOfWork:
    def __init__(self, image_generations: FakeImageGenerationRepository) -> None:
        self.image_generations = image_generations
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        return None


def storage_settings(**overrides: object) -> Settings:
    values = {
        "_env_file": None,
        "storage_provider": "supabase",
        "storage_bucket": "creator-images",
        "storage_signed_url_expires_seconds": 600,
        "storage_max_object_bytes": 128,
        "supabase_url": "https://creator-test.supabase.co",
        "supabase_service_role_key": "service-role-key",
        "supabase_auth_timeout_seconds": 4,
    }
    values.update(overrides)
    return Settings(**values)


def job_record(content_id: UUID | None = None) -> GenerationJobRecord:
    return GenerationJobRecord(
        id=uuid4(),
        workspace_id=uuid4(),
        generation_id=uuid4(),
        content_id=content_id or uuid4(),
        status=GenerationJobStatus.PROCESSING,
        external_id=None,
        attempt_count=1,
        max_attempts=3,
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


def generated_image() -> GeneratedImage:
    return GeneratedImage(
        content=b"image-bytes",
        mime_type="image/png",
        width=2,
        height=3,
        model="gemini-image",
        prompt="Generate an image",
        metadata={"provider": "gemini"},
    )


def test_immutable_image_path_is_scoped_by_user_content_and_version() -> None:
    content_id = uuid4()

    path = immutable_image_path(
        user_external_id="principal-123",
        content_id=content_id,
        version_number=2,
        mime_type="image/png",
    )

    assert path == f"users/principal-123/contents/{content_id}/versions/2/image.png"


def test_immutable_image_path_rejects_unsafe_user_segment() -> None:
    with pytest.raises(StorageValidationError):
        immutable_image_path(
            user_external_id="../other-user",
            content_id=uuid4(),
            version_number=1,
            mime_type="image/png",
        )


def test_supabase_storage_uploads_and_returns_signed_url_without_real_network() -> None:
    opener = FakeStorageOpener(
        [
            FakeStorageResponse(status=200),
            FakeStorageResponse(b'{"signedURL":"/object/sign/creator-images/path.png?token=abc"}'),
        ]
    )
    provider = SupabaseStorageProvider(storage_settings(), opener=opener)

    stored = provider.upload(
        UploadObjectRequest(
            path="users/u/contents/c/versions/1/image.png", content=b"abc", mime_type="image/png"
        )
    )

    upload_request = opener.requests[0]
    sign_request = opener.requests[1]
    assert stored.path == "users/u/contents/c/versions/1/image.png"
    assert stored.url == (
        "https://creator-test.supabase.co/storage/v1/object/sign/creator-images/path.png?token=abc"
    )
    assert upload_request.full_url.endswith(
        "/storage/v1/object/creator-images/users/u/contents/c/versions/1/image.png"
    )
    assert upload_request.get_header("X-upsert") == "false"
    assert sign_request.full_url.endswith(
        "/storage/v1/object/sign/creator-images/users/u/contents/c/versions/1/image.png"
    )
    assert opener.timeouts == [4, 4]


def test_supabase_storage_rejects_checksum_mismatch_before_upload() -> None:
    opener = FakeStorageOpener([])
    provider = SupabaseStorageProvider(storage_settings(), opener=opener)

    with pytest.raises(StorageValidationError):
        provider.upload(
            UploadObjectRequest(
                path="users/u/contents/c/versions/1/image.png",
                content=b"abc",
                mime_type="image/png",
                checksum_sha256="wrong",
            )
        )

    assert opener.requests == []


def test_local_storage_persists_objects_across_provider_instances(tmp_path: Path) -> None:
    settings = storage_settings(storage_provider="local", local_storage_root=str(tmp_path))
    first_provider = LocalStorageProvider(settings)

    stored = first_provider.upload(
        UploadObjectRequest(
            path="users/u/contents/c/versions/1/image.png", content=b"abc", mime_type="image/png"
        )
    )
    second_provider = LocalStorageProvider(settings)

    assert stored.url == second_provider.get_url(stored.path)


def test_local_storage_delete_is_idempotent_for_retention_purge(tmp_path: Path) -> None:
    settings = storage_settings(storage_provider="local", local_storage_root=str(tmp_path))
    provider = LocalStorageProvider(settings)
    stored = provider.upload(
        UploadObjectRequest(
            path="users/u/contents/c/versions/1/image.png", content=b"abc", mime_type="image/png"
        )
    )

    provider.delete(stored.path)
    provider.delete(stored.path)

    with pytest.raises(StorageUrlError):
        provider.get_url(stored.path)


def test_persist_generated_image_uploads_before_completing_job() -> None:
    repository = FakeImageGenerationRepository()
    unit_of_work = FakeUnitOfWork(repository)
    storage = FakeStorage()
    job = job_record()

    image = persist_generated_image(
        unit_of_work=unit_of_work,
        storage=storage,
        job=job,
        user=user_record(),
        image=generated_image(),
    )

    assert storage.uploads[0].path == (
        f"users/principal-123/contents/{job.content_id}/versions/3/image.png"
    )
    assert repository.completed[0].storage_path == storage.uploads[0].path
    assert repository.completed[0].version_number == 3
    assert image.metadata["storage_provider"] == "fake"
    assert unit_of_work.commits == 1


def test_persist_generated_image_marks_job_failed_when_upload_fails() -> None:
    repository = FakeImageGenerationRepository()
    unit_of_work = FakeUnitOfWork(repository)

    with pytest.raises(StorageUploadError):
        persist_generated_image(
            unit_of_work=unit_of_work,
            storage=FakeStorage(fail_upload=True),
            job=job_record(),
            user=user_record(),
            image=generated_image(),
        )

    assert repository.completed == []
    assert repository.failed[0]["failure_code"] == "STORAGE_UPLOAD_FAILED"
    assert unit_of_work.commits == 1


def test_persist_generated_image_deletes_uploaded_object_when_completion_fails() -> None:
    repository = FakeImageGenerationRepository(complete_error=RuntimeError("db failed"))
    unit_of_work = FakeUnitOfWork(repository)
    storage = FakeStorage()

    with pytest.raises(RuntimeError):
        persist_generated_image(
            unit_of_work=unit_of_work,
            storage=storage,
            job=job_record(),
            user=user_record(),
            image=generated_image(),
        )

    assert storage.deleted == [storage.uploads[0].path]
    assert unit_of_work.commits == 0
