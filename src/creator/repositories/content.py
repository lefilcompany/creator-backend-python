from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from creator.repositories.common import JsonObject, Page, PageRequest


@dataclass(frozen=True, slots=True)
class ContentRecord:
    id: UUID
    workspace_id: UUID
    created_by_user_id: UUID | None
    content_type: str
    title: str | None
    payload: JsonObject
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class ContentFilters:
    workspace_id: UUID | None = None
    content_type: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    include_deleted: bool = False


class ContentRepository(Protocol):
    def add(
        self,
        *,
        workspace_id: UUID,
        created_by_user_id: UUID | None,
        title: str | None = None,
        payload: JsonObject | None = None,
    ) -> ContentRecord: ...

    def get_by_id_for_user(
        self,
        *,
        user_id: UUID,
        content_id: UUID,
        include_deleted: bool = False,
    ) -> ContentRecord | None: ...

    def list_for_user(
        self,
        *,
        user_id: UUID,
        filters: ContentFilters | None = None,
        page: PageRequest | None = None,
    ) -> Page[ContentRecord]: ...

    def update(
        self,
        content_id: UUID,
        *,
        title: str | None = None,
        payload: JsonObject | None = None,
    ) -> ContentRecord: ...

    def soft_delete(self, content_id: UUID) -> None: ...
