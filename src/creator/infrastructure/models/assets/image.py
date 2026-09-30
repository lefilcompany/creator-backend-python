from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from creator.infrastructure import schema_models as _schema_models  # noqa: F401
from creator.infrastructure.db import Base

from ..types import timestamp_tz, uuid_pk


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
