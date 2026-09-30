from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from creator.domain.agent_workflow import (
    AgentWorkflowStatus,
    AgentWorkflowStepRole,
    AgentWorkflowStepStatus,
    HumanReviewMode,
)
from creator.domain.generation import GenerationJobStatus

# Importing the schema slices registers their mapped tables in Base.metadata.
# The alias intentionally prevents polluting the public model namespace.
from creator.infrastructure import schema_models as _schema_models  # noqa: F401,E402
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
    TEXT = "TEXT"


class GenerationType(StrEnum):
    IMAGE = "IMAGE"
    TEXT = "TEXT"


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
agent_workflow_status_enum = SQLEnum(
    AgentWorkflowStatus,
    name="agent_workflow_status",
    native_enum=True,
    values_callable=enum_values,
    validate_strings=True,
)
agent_workflow_step_status_enum = SQLEnum(
    AgentWorkflowStepStatus,
    name="agent_workflow_step_status",
    native_enum=True,
    values_callable=enum_values,
    validate_strings=True,
)
agent_workflow_step_role_enum = SQLEnum(
    AgentWorkflowStepRole,
    name="agent_workflow_step_role",
    native_enum=True,
    values_callable=enum_values,
    validate_strings=True,
)
human_review_mode_enum = SQLEnum(
    HumanReviewMode,
    name="human_review_mode",
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
