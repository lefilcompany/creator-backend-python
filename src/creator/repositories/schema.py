from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from creator.repositories.common import Page, PageRequest


@dataclass(frozen=True, slots=True)
class CampaignRecord:
    id: UUID
    workspace_id: UUID
    created_by: UUID
    name: str
    description: str | None
    target_audience: str | None
    objectives: str | None
    voice: str | None
    start_at: datetime | None
    end_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class CampaignRepository(Protocol):
    def add(
        self,
        *,
        workspace_id: UUID,
        created_by: UUID,
        name: str,
        description: str | None = None,
        target_audience: str | None = None,
        objectives: str | None = None,
        voice: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> CampaignRecord: ...

    def get_for_user(self, *, user_id: UUID, campaign_id: UUID) -> CampaignRecord | None: ...

    def list_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[CampaignRecord]: ...


@dataclass(frozen=True, slots=True)
class PlanningRecord:
    id: UUID
    brand_id: UUID
    campaign_id: UUID
    persona_id: UUID
    created_by: UUID
    info: str | None
    static_amount: int | None
    carousel_amount: int | None
    stories_amount: int | None
    special_dates: str | None
    start_period: datetime | None
    end_period: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class PlanningRepository(Protocol):
    def add(self, *, created_by: UUID, **fields: object) -> PlanningRecord: ...
    def list_for_user(
        self, *, user_id: UUID, campaign_id: UUID | None = None, page: PageRequest | None = None
    ) -> Page[PlanningRecord]: ...


@dataclass(frozen=True, slots=True)
class PersonaRecord:
    id: UUID
    brand_id: UUID
    created_by: UUID
    name: str
    age: int | None
    gender: str | None
    main_goal: str | None
    challenge: str | None
    interest: str | None
    routine: str | None
    journey: str | None
    trigger: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class PersonaRepository(Protocol):
    def add(self, *, created_by: UUID, **fields: object) -> PersonaRecord: ...
    def list_for_user(
        self, *, user_id: UUID, brand_id: UUID | None = None, page: PageRequest | None = None
    ) -> Page[PersonaRecord]: ...


@dataclass(frozen=True, slots=True)
class GeneratedImageRecord:
    id: UUID
    workspace_id: UUID
    design_structure_id: UUID
    signed_url: str | None
    size: str | None
    resolution: str | None
    image_ratio: str | None
    status: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class GeneratedImageRepository(Protocol):
    def get_for_user(self, *, user_id: UUID, image_id: UUID) -> GeneratedImageRecord | None: ...


@dataclass(frozen=True, slots=True)
class PostStructureRecord:
    id: UUID
    workspace_id: UUID
    planning_id: UUID
    created_by: UUID
    title: str | None
    objective: str | None
    big_idea: str | None
    main_message: str | None
    headline: str | None
    image_cta: str | None
    art_guiding: str | None
    status: str | None
    format: str | None
    ratio: str | None
    resolution: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class PostStructureRepository(Protocol):
    def add(
        self, *, workspace_id: UUID, planning_id: UUID, created_by: UUID, **fields: str | None
    ) -> PostStructureRecord: ...
    def get_for_user(
        self, *, user_id: UUID, post_structure_id: UUID
    ) -> PostStructureRecord | None: ...
    def list_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID | None = None,
        planning_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[PostStructureRecord]: ...

    def update(
        self, *, post_structure_id: UUID, fields: dict[str, str | None]
    ) -> PostStructureRecord | None: ...

    def soft_delete(self, *, post_structure_id: UUID) -> bool: ...


@dataclass(frozen=True, slots=True)
class BrandAssetRecord:
    id: UUID
    brand_id: UUID
    type: str
    file_url: str
    file_name: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class BrandAssetRepository(Protocol):
    def add(
        self,
        *,
        brand_id: UUID,
        type: str,
        file_url: str,
        file_name: str | None = None,
        description: str | None = None,
    ) -> BrandAssetRecord: ...
    def get_for_user(self, *, user_id: UUID, asset_id: UUID) -> BrandAssetRecord | None: ...
    def list_for_user(
        self, *, user_id: UUID, brand_id: UUID | None = None, page: PageRequest | None = None
    ) -> Page[BrandAssetRecord]: ...
