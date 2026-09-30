from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from creator.infrastructure import schema_models as _schema_models  # noqa: F401
from creator.infrastructure.db import Base

from ..types import timestamp_tz, uuid_pk


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (Index("ix_workspaces_deleted_at", "deleted_at"),)

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
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
