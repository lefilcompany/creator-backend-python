from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from creator.domain.generation import GenerationJobStatus
from creator.infrastructure.db import Base


def enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_type]


class GlobalRole(StrEnum):
    ADMIN = "admin"
    GESTOR = "gestor"
    MEMBRO = "membro"


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class ContentType(StrEnum):
    IMAGE = "IMAGE"


class GenerationType(StrEnum):
    IMAGE = "IMAGE"


uuid_pk = PGUUID(as_uuid=True)
timestamp_tz = DateTime(timezone=True)

global_role_enum = SQLEnum(
    GlobalRole,
    name="global_role",
    native_enum=True,
    values_callable=enum_values,
    validate_strings=True,
)
workspace_role_enum = SQLEnum(
    WorkspaceRole,
    name="workspace_role",
    native_enum=True,
    values_callable=enum_values,
    validate_strings=True,
)
content_type_enum = SQLEnum(
    ContentType,
    name="content_type",
    native_enum=True,
    values_callable=enum_values,
    validate_strings=True,
)
generation_type_enum = SQLEnum(
    GenerationType,
    name="generation_type",
    native_enum=True,
    values_callable=enum_values,
    validate_strings=True,
)
generation_job_status_enum = SQLEnum(
    GenerationJobStatus,
    name="generation_job_status",
    native_enum=True,
    values_callable=enum_values,
    validate_strings=True,
)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("external_id", name="uq_users_external_id"),
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_deleted_at", "deleted_at"),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(255))
    global_role: Mapped[GlobalRole] = mapped_column(
        global_role_enum,
        nullable=False,
        server_default=text("'membro'"),
    )
    created_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[object | None] = mapped_column(timestamp_tz)


class Settings(Base):
    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_settings_user_id"),
        Index("ix_settings_user_id", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    preferences: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (Index("ix_workspaces_deleted_at", "deleted_at"),)

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[object | None] = mapped_column(timestamp_tz)


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_memberships_deleted_after_created",
        ),
        Index("ix_workspace_memberships_user_id", "user_id"),
        Index("ix_workspace_memberships_workspace_id", "workspace_id"),
        Index(
            "uq_workspace_memberships_active_user_workspace",
            "user_id",
            "workspace_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[WorkspaceRole] = mapped_column(workspace_role_enum, nullable=False)
    created_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[object | None] = mapped_column(timestamp_tz)


class Content(Base):
    __tablename__ = "contents"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_contents_id_workspace_id"),
        CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_contents_deleted_after_created",
        ),
        Index("ix_contents_workspace_filter", "workspace_id", "type", "deleted_at", "created_at"),
        Index("ix_contents_created_by_user_id", "created_by_user_id"),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    content_type: Mapped[ContentType] = mapped_column(
        "type",
        content_type_enum,
        nullable=False,
        server_default=text("'IMAGE'"),
    )
    title: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[object | None] = mapped_column(timestamp_tz)


class Generation(Base):
    __tablename__ = "generations"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_generations_id_workspace_id"),
        UniqueConstraint(
            "id", "workspace_id", "content_id", name="uq_generations_id_workspace_content_id"
        ),
        ForeignKeyConstraint(
            ["content_id", "workspace_id"],
            ["contents.id", "contents.workspace_id"],
            name="fk_generations_content_workspace",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "char_length(prompt) BETWEEN 1 AND 20000", name="ck_generations_prompt_length"
        ),
        CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_generations_deleted_after_created",
        ),
        Index("ix_generations_requested_by_user_id", "requested_by_user_id"),
        Index(
            "ix_generations_workspace_filter", "workspace_id", "type", "deleted_at", "created_at"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    content_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    generation_type: Mapped[GenerationType] = mapped_column(
        "type",
        generation_type_enum,
        nullable=False,
        server_default=text("'IMAGE'"),
    )
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[object | None] = mapped_column(timestamp_tz)


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["generation_id", "workspace_id"],
            ["generations.id", "generations.workspace_id"],
            name="fk_generation_jobs_generation_workspace",
            ondelete="CASCADE",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_generation_jobs_attempt_count_non_negative"),
        CheckConstraint("max_attempts > 0", name="ck_generation_jobs_max_attempts_positive"),
        CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_generation_jobs_deleted_after_created",
        ),
        Index("ix_generation_jobs_generation_id", "generation_id"),
        Index(
            "ix_generation_jobs_workspace_status_created_at", "workspace_id", "status", "created_at"
        ),
        Index("ix_generation_jobs_status_created_at", "status", "created_at"),
        Index(
            "uq_generation_jobs_external_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    generation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[GenerationJobStatus] = mapped_column(
        generation_job_status_enum,
        nullable=False,
        server_default=text("'PENDING'"),
    )
    external_id: Mapped[str | None] = mapped_column(String(255))
    attempt_count: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[object | None] = mapped_column(timestamp_tz)
    completed_at: Mapped[object | None] = mapped_column(timestamp_tz)
    failed_at: Mapped[object | None] = mapped_column(timestamp_tz)
    created_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[object | None] = mapped_column(timestamp_tz)


class GenerationJobStatusEvent(Base):
    __tablename__ = "generation_job_status_events"
    __table_args__ = (
        CheckConstraint(
            "previous_status IS NULL OR previous_status <> status",
            name="ck_generation_job_status_events_status_changed",
        ),
        Index(
            "ix_generation_job_status_events_job_occurred_at", "generation_job_id", "occurred_at"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    generation_job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("generation_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    previous_status: Mapped[GenerationJobStatus | None] = mapped_column(generation_job_status_enum)
    status: Mapped[GenerationJobStatus] = mapped_column(generation_job_status_enum, nullable=False)
    occurred_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
    )


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (
        UniqueConstraint("generation_id", name="uq_images_generation_id"),
        UniqueConstraint("storage_path", name="uq_images_storage_path"),
        ForeignKeyConstraint(
            ["content_id", "workspace_id"],
            ["contents.id", "contents.workspace_id"],
            name="fk_images_content_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["generation_id", "workspace_id", "content_id"],
            ["generations.id", "generations.workspace_id", "generations.content_id"],
            name="fk_images_generation_workspace_content",
            ondelete="RESTRICT",
        ),
        CheckConstraint("version_number > 0", name="ck_images_version_number_positive"),
        CheckConstraint(
            "mime_type IN ('image/png', 'image/jpeg', 'image/webp')",
            name="ck_images_mime_type_supported",
        ),
        CheckConstraint("width > 0", name="ck_images_width_positive"),
        CheckConstraint("height > 0", name="ck_images_height_positive"),
        CheckConstraint("char_length(prompt) BETWEEN 1 AND 20000", name="ck_images_prompt_length"),
        CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at", name="ck_images_deleted_after_created"
        ),
        Index("ix_images_content_version", "content_id", "version_number"),
        Index("ix_images_workspace_filter", "workspace_id", "deleted_at", "created_at"),
        Index(
            "uq_images_active_content_version",
            "content_id",
            "version_number",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    content_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    generation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    public_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    width: Mapped[int] = mapped_column(nullable=False)
    height: Mapped[int] = mapped_column(nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[object] = mapped_column(
        timestamp_tz,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    deleted_at: Mapped[object | None] = mapped_column(timestamp_tz)
