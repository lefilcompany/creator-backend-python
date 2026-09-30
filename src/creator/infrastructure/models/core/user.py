from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from creator.infrastructure import schema_models as _schema_models  # noqa: F401
from creator.infrastructure.db import Base

from ..enums import (
    GlobalRole,
    global_role_enum,
)
from ..types import timestamp_tz, uuid_pk


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
    email: Mapped[str | None] = mapped_column(String(50))
    display_name: Mapped[str | None] = mapped_column(String(50))
    cpf: Mapped[str | None] = mapped_column(String(11))
    cnpj: Mapped[str | None] = mapped_column(String(14))
    bio: Mapped[str | None] = mapped_column(String(350))
    avatar_url: Mapped[str | None] = mapped_column(String)
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
