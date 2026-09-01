from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from creator.domain.generation import GenerationJobStatus
from creator.repositories.common import JsonObject, Page, PageRequest
from creator.repositories.user import UserRecord


@dataclass(frozen=True, slots=True)
class GenerationJobRecord:
    id: UUID
    workspace_id: UUID
    generation_id: UUID
    content_id: UUID
    status: GenerationJobStatus
    external_id: str | None
    attempt_count: int
    max_attempts: int
    failure_code: str | None
    failure_message: str | None
    queued_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class GenerationHistoryFilters:
    workspace_id: UUID | None = None
    content_id: UUID | None = None
    status: GenerationJobStatus | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    include_deleted: bool = False


@dataclass(frozen=True, slots=True)
class ImageRecord:
    id: UUID
    workspace_id: UUID
    content_id: UUID
    generation_id: UUID
    version_number: int
    storage_path: str
    public_url: str
    mime_type: str
    width: int
    height: int
    model: str
    prompt: str
    metadata: JsonObject
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class ImageMetadata:
    storage_path: str
    public_url: str
    mime_type: str
    width: int
    height: int
    model: str
    prompt: str
    version_number: int | None = None
    metadata: JsonObject = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GenerationJobStatusEventRecord:
    id: UUID
    generation_job_id: UUID
    previous_status: GenerationJobStatus | None
    status: GenerationJobStatus
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ImageGenerationStatusRecord:
    job: GenerationJobRecord
    parameters: JsonObject
    image: ImageRecord | None = None


@dataclass(frozen=True, slots=True)
class ImageGenerationWorkItem:
    job: GenerationJobRecord
    model: str
    prompt: str
    parameters: JsonObject
    requested_by_user: UserRecord


class ImageGenerationRepository(Protocol):
    def create_image_generation(
        self,
        *,
        workspace_id: UUID,
        content_id: UUID,
        requested_by_user_id: UUID | None,
        model: str,
        prompt: str,
        parameters: JsonObject | None = None,
        external_id: str | None = None,
    ) -> GenerationJobRecord: ...

    def get_job_for_user(
        self,
        *,
        user_id: UUID,
        job_id: UUID,
        include_deleted: bool = False,
    ) -> GenerationJobRecord | None: ...

    def list_history_for_user(
        self,
        *,
        user_id: UUID,
        filters: GenerationHistoryFilters | None = None,
        page: PageRequest | None = None,
    ) -> Page[GenerationJobRecord]: ...

    def claim_next_pending(
        self, *, workspace_id: UUID | None = None
    ) -> GenerationJobRecord | None: ...

    def next_image_version(self, content_id: UUID) -> int: ...

    def get_status_for_user(
        self,
        *,
        user_id: UUID,
        job_id: UUID,
        include_deleted: bool = False,
    ) -> ImageGenerationStatusRecord | None: ...

    def get_status_by_external_id_for_user(
        self,
        *,
        user_id: UUID,
        external_id: str,
        include_deleted: bool = False,
    ) -> ImageGenerationStatusRecord | None: ...

    def claim_pending_by_id(self, job_id: UUID) -> ImageGenerationWorkItem | None: ...

    def get_image_for_user(
        self,
        *,
        user_id: UUID,
        image_id: UUID,
        include_deleted: bool = False,
    ) -> ImageRecord | None: ...

    def complete_job(self, job_id: UUID, image: ImageMetadata) -> ImageRecord: ...

    def fail_job(
        self,
        job_id: UUID,
        *,
        failure_code: str,
        failure_message: str,
    ) -> GenerationJobRecord: ...
