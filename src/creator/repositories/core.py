from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from creator.repositories.common import JsonObject, Page, PageRequest


@dataclass(frozen=True, slots=True)
class BrandRecord:
    id: UUID
    workspace_id: UUID
    created_by_user_id: UUID | None
    name: str
    description: str | None
    brand_voice: str | None
    metadata: JsonObject
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class ProjectRecord:
    id: UUID
    workspace_id: UUID
    brand_id: UUID | None
    created_by_user_id: UUID | None
    name: str
    description: str | None
    status: str
    metadata: JsonObject
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class GenerationRecord:
    id: UUID
    workspace_id: UUID
    content_id: UUID
    brand_id: UUID | None
    project_id: UUID | None
    requested_by_user_id: UUID | None
    generation_type: str
    model: str
    prompt: str
    parameters: JsonObject
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class AssetRecord:
    id: UUID
    workspace_id: UUID
    brand_id: UUID | None
    project_id: UUID | None
    content_id: UUID | None
    uploaded_by_user_id: UUID | None
    asset_type: str
    storage_path: str
    public_url: str | None
    mime_type: str
    byte_size: int
    checksum: str | None
    metadata: JsonObject
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class BrandSettingsRecord:
    id: UUID
    workspace_id: UUID
    brand_id: UUID
    voice_settings: JsonObject
    visual_settings: JsonObject
    generation_defaults: JsonObject
    metadata: JsonObject
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class BrandRepository(Protocol):
    def add(
        self,
        *,
        workspace_id: UUID,
        created_by_user_id: UUID | None,
        name: str,
        description: str | None = None,
        brand_voice: str | None = None,
        metadata: JsonObject | None = None,
    ) -> BrandRecord: ...

    def get_for_user(
        self,
        *,
        user_id: UUID,
        brand_id: UUID,
        include_deleted: bool = False,
    ) -> BrandRecord | None: ...

    def list_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[BrandRecord]: ...

    def update(
        self,
        *,
        user_id: UUID,
        brand_id: UUID,
        name: str | None = None,
        description: str | None = None,
        brand_voice: str | None = None,
        metadata: JsonObject | None = None,
    ) -> BrandRecord: ...

    def soft_delete(self, *, user_id: UUID, brand_id: UUID) -> None: ...


class ProjectRepository(Protocol):
    def add(
        self,
        *,
        workspace_id: UUID,
        brand_id: UUID | None,
        created_by_user_id: UUID | None,
        name: str,
        description: str | None = None,
        status: str = "ACTIVE",
        metadata: JsonObject | None = None,
    ) -> ProjectRecord: ...

    def get_for_user(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        include_deleted: bool = False,
    ) -> ProjectRecord | None: ...

    def list_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID | None = None,
        brand_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[ProjectRecord]: ...

    def update(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        metadata: JsonObject | None = None,
    ) -> ProjectRecord: ...

    def soft_delete(self, *, user_id: UUID, project_id: UUID) -> None: ...


class GenerationRepository(Protocol):
    def add(
        self,
        *,
        workspace_id: UUID,
        content_id: UUID,
        requested_by_user_id: UUID | None,
        model: str,
        prompt: str,
        generation_type: str = "TEXT",
        brand_id: UUID | None = None,
        project_id: UUID | None = None,
        parameters: JsonObject | None = None,
    ) -> GenerationRecord: ...

    def get_for_user(
        self,
        *,
        user_id: UUID,
        generation_id: UUID,
        include_deleted: bool = False,
    ) -> GenerationRecord | None: ...

    def list_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID | None = None,
        content_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[GenerationRecord]: ...

    def update(
        self,
        *,
        user_id: UUID,
        generation_id: UUID,
        model: str | None = None,
        prompt: str | None = None,
        parameters: JsonObject | None = None,
    ) -> GenerationRecord: ...

    def soft_delete(self, *, user_id: UUID, generation_id: UUID) -> None: ...


class AssetRepository(Protocol):
    def add(
        self,
        *,
        workspace_id: UUID,
        uploaded_by_user_id: UUID | None,
        asset_type: str,
        storage_path: str,
        mime_type: str,
        byte_size: int,
        brand_id: UUID | None = None,
        project_id: UUID | None = None,
        content_id: UUID | None = None,
        public_url: str | None = None,
        checksum: str | None = None,
        metadata: JsonObject | None = None,
    ) -> AssetRecord: ...

    def get_for_user(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
        include_deleted: bool = False,
    ) -> AssetRecord | None: ...

    def list_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID | None = None,
        brand_id: UUID | None = None,
        project_id: UUID | None = None,
        content_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[AssetRecord]: ...

    def update(
        self,
        *,
        user_id: UUID,
        asset_id: UUID,
        asset_type: str | None = None,
        public_url: str | None = None,
        metadata: JsonObject | None = None,
    ) -> AssetRecord: ...

    def soft_delete(self, *, user_id: UUID, asset_id: UUID) -> None: ...


class BrandSettingsRepository(Protocol):
    def get_for_user(
        self,
        *,
        user_id: UUID,
        brand_id: UUID,
        include_deleted: bool = False,
    ) -> BrandSettingsRecord | None: ...

    def upsert(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        brand_id: UUID,
        voice_settings: JsonObject | None = None,
        visual_settings: JsonObject | None = None,
        generation_defaults: JsonObject | None = None,
        metadata: JsonObject | None = None,
    ) -> BrandSettingsRecord: ...

    def update(
        self,
        *,
        user_id: UUID,
        brand_id: UUID,
        voice_settings: JsonObject | None = None,
        visual_settings: JsonObject | None = None,
        generation_defaults: JsonObject | None = None,
        metadata: JsonObject | None = None,
    ) -> BrandSettingsRecord: ...

    def soft_delete(self, *, user_id: UUID, brand_id: UUID) -> None: ...
