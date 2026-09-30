from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    DateTime,
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


class AgentWorkflowStep(Base):
    __tablename__ = "agent_workflow_steps"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "sequence_number", "attempt", name="uq_agent_workflow_steps_attempt"
        ),
        ForeignKeyConstraint(
            ["run_id", "workspace_id"],
            ["agent_workflow_runs.id", "agent_workflow_runs.workspace_id"],
            name="fk_agent_workflow_steps_run_workspace",
            ondelete="CASCADE",
        ),
        Index("ix_agent_workflow_steps_run_sequence", "run_id", "sequence_number"),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    role: Mapped[AgentWorkflowStepRole] = mapped_column(
        agent_workflow_step_role_enum, nullable=False
    )
    status: Mapped[AgentWorkflowStepStatus] = mapped_column(
        agent_workflow_step_status_enum, nullable=False, server_default=text("'PENDING'")
    )
    attempt: Mapped[int] = mapped_column(nullable=False, server_default=text("1"))
    input_json: Mapped[dict[str, object]] = mapped_column(
        "input", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    output_json: Mapped[dict[str, object]] = mapped_column(
        "output", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    prompt: Mapped[str | None] = mapped_column(Text)
    prompt_template_id: Mapped[str | None] = mapped_column(String(255))
    prompt_template_version: Mapped[str | None] = mapped_column(String(32))
    input_hash: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(255))
    decision: Mapped[str | None] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[object | None] = mapped_column(timestamp_tz)
    completed_at: Mapped[object | None] = mapped_column(timestamp_tz)
    created_at: Mapped[object] = mapped_column(
        timestamp_tz, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        timestamp_tz, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[object | None] = mapped_column(timestamp_tz)
