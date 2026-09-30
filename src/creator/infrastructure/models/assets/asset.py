from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
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


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("storage_path", name="uq_assets_storage_path"),
        ForeignKeyConstraint(
            ["brand_id", "workspace_id"],
            ["brands.id", "brands.workspace_id"],
            name="fk_assets_brand_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "workspace_id"],
            ["projects.id", "projects.workspace_id"],
            name="fk_assets_project_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["content_id", "workspace_id"],
            ["contents.id", "contents.workspace_id"],
            name="fk_assets_content_workspace",
            ondelete="RESTRICT",
        ),
        CheckConstraint("byte_size >= 0", name="ck_assets_byte_size_non_negative"),
        CheckConstraint("char_length(asset_type) BETWEEN 1 AND 100", name="ck_assets_type_length"),
        CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at", name="ck_assets_deleted_after_created"
        ),
        Index("ix_assets_workspace_filter", "workspace_id", "deleted_at", "created_at"),
        Index("ix_assets_brand_id", "brand_id"),
        Index("ix_assets_project_id", "project_id"),
        Index("ix_assets_content_id", "content_id"),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    brand_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    project_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    content_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    asset_type: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    public_url: Mapped[str | None] = mapped_column(String(2048))
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(255))
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
