from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
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

from creator.domain.agent_workflow import (
    AgentWorkflowStepRole,
    AgentWorkflowStepStatus,
)
from creator.infrastructure import schema_models as _schema_models  # noqa: F401
from creator.infrastructure.db import Base

from ..enums import (
    agent_workflow_step_role_enum,
    agent_workflow_step_status_enum,
)
from ..types import timestamp_tz, uuid_pk


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
    output_hash: Mapped[str | None] = mapped_column(String(64))
    schema_name: Mapped[str | None] = mapped_column(String(100))
    schema_version: Mapped[str | None] = mapped_column(String(32))
    predecessor_step_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    correlation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
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
