from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
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

from ..enums import (
    ContentType,
    content_type_enum,
)
from ..types import timestamp_tz, uuid_pk


class Content(Base):
    __tablename__ = "contents"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_contents_id_workspace_id"),
        ForeignKeyConstraint(
            ["brand_id", "workspace_id"],
            ["brands.id", "brands.workspace_id"],
            name="fk_contents_brand_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "workspace_id"],
            ["projects.id", "projects.workspace_id"],
            name="fk_contents_project_workspace",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_contents_deleted_after_created",
        ),
        Index("ix_contents_workspace_filter", "workspace_id", "type", "deleted_at", "created_at"),
        Index("ix_contents_workspace_created_id", "workspace_id", "deleted_at", "created_at", "id"),
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
    brand_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    project_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
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
