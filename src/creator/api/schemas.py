from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Meta(BaseModel):
    request_id: UUID


class SuccessResponse(BaseModel):
    success: bool = True
    data: Any
    meta: Meta


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
    meta: Meta


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=4096, repr=False)


class AuthSignupRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=4096, repr=False)


class GenerateImageRequest(BaseModel):
    content_id: UUID
    style: Literal["photographic", "illustration", "product_render"] | None = None


class GenerateContentRequest(BaseModel):
    workspace_id: UUID
    topic: str = Field(min_length=1, max_length=255)
    audience: str = Field(min_length=1, max_length=255)
    tone: (
        Literal["professional", "friendly", "persuasive", "educational", "formal", "casual"] | None
    ) = None
    content_type: Literal[
        "social_post",
        "email",
        "ad_copy",
        "landing_page",
        "blog_post",
        "product_description",
    ]
    brand_voice: str | None = Field(default=None, min_length=1, max_length=1_000)


class SettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand_name: str | None = Field(default=None, max_length=255)
    segment: str | None = Field(default=None, max_length=255)
    tone: (
        Literal["professional", "friendly", "persuasive", "educational", "formal", "casual"] | None
    ) = None
    voice: str | None = Field(default=None, min_length=1, max_length=1_000)
    visual_style: Literal["photographic", "illustration", "product_render"] | None = None
    default_preferences: dict[str, object] | None = None


class GenerateTextRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)
    temperature: float = Field(default=0.7, ge=0, le=2)


class UserCreateRequest(BaseModel):
    external_id: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    display_name: str | None = Field(default=None, max_length=255)
    global_role: Literal["admin", "gestor", "membro"] = "membro"


class UserUpdateRequest(BaseModel):
    email: str | None = Field(default=None, max_length=320)
    display_name: str | None = Field(default=None, max_length=255)
    global_role: Literal["admin", "gestor", "membro"] | None = None


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class WorkspaceUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class BrandCreateRequest(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    brand_voice: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class BrandUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    brand_voice: str | None = None
    metadata: dict[str, object] | None = None


class ProjectCreateRequest(BaseModel):
    workspace_id: UUID
    brand_id: UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: Literal["ACTIVE", "ARCHIVED"] = "ACTIVE"
    metadata: dict[str, object] = Field(default_factory=dict)


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: Literal["ACTIVE", "ARCHIVED"] | None = None
    metadata: dict[str, object] | None = None


class ContentCreateRequest(BaseModel):
    workspace_id: UUID
    brand_id: UUID | None = None
    project_id: UUID | None = None
    type: Literal["IMAGE", "TEXT"] = "IMAGE"
    title: str | None = Field(default=None, max_length=255)
    payload: dict[str, object] = Field(default_factory=dict)


class ContentUpdateRequest(BaseModel):
    brand_id: UUID | None = None
    project_id: UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    payload: dict[str, object] | None = None


class GenerationCreateRequest(BaseModel):
    workspace_id: UUID
    content_id: UUID
    brand_id: UUID | None = None
    project_id: UUID | None = None
    type: Literal["IMAGE", "TEXT"] = "TEXT"
    model: str = Field(min_length=1, max_length=255)
    prompt: str = Field(min_length=1, max_length=20_000)
    parameters: dict[str, object] = Field(default_factory=dict)


class GenerationUpdateRequest(BaseModel):
    model: str | None = Field(default=None, min_length=1, max_length=255)
    prompt: str | None = Field(default=None, min_length=1, max_length=20_000)
    parameters: dict[str, object] | None = None


class AssetCreateRequest(BaseModel):
    workspace_id: UUID
    brand_id: UUID | None = None
    project_id: UUID | None = None
    content_id: UUID | None = None
    asset_type: str = Field(min_length=1, max_length=100)
    storage_path: str = Field(min_length=1, max_length=1024)
    public_url: str | None = Field(default=None, max_length=2048)
    mime_type: str = Field(min_length=1, max_length=100)
    byte_size: int = Field(ge=0)
    checksum: str | None = Field(default=None, max_length=255)
    metadata: dict[str, object] = Field(default_factory=dict)


class AssetUpdateRequest(BaseModel):
    asset_type: str | None = Field(default=None, min_length=1, max_length=100)
    public_url: str | None = Field(default=None, max_length=2048)
    metadata: dict[str, object] | None = None


class BrandSettingsUpsertRequest(BaseModel):
    workspace_id: UUID
    voice_settings: dict[str, object] = Field(default_factory=dict)
    visual_settings: dict[str, object] = Field(default_factory=dict)
    generation_defaults: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)


class BrandSettingsUpdateRequest(BaseModel):
    voice_settings: dict[str, object] | None = None
    visual_settings: dict[str, object] | None = None
    generation_defaults: dict[str, object] | None = None
    metadata: dict[str, object] | None = None
