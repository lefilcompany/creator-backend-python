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

from creator.domain.agent_workflow import (
    AgentWorkflowStatus,
    HumanReviewMode,
)
from creator.infrastructure import schema_models as _schema_models  # noqa: F401
from creator.infrastructure.db import Base

from ..enums import (
    agent_workflow_status_enum,
    human_review_mode_enum,
)
from ..types import timestamp_tz, uuid_pk


class AgentWorkflowRun(Base):
    __tablename__ = "agent_workflow_runs"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "workspace_id",
            name="uq_agent_workflow_runs_id_workspace",
        ),
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_agent_workflow_runs_workspace_idempotency_key",
        ),
        ForeignKeyConstraint(
            ["content_id", "workspace_id"],
            ["contents.id", "contents.workspace_id"],
            name="fk_agent_workflow_runs_content_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["brand_id", "workspace_id"],
            ["brands.id", "brands.workspace_id"],
            name="fk_agent_workflow_runs_brand_workspace",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_agent_workflow_runs_workspace_status_created",
            "workspace_id",
            "status",
            "created_at",
        ),
        CheckConstraint(
            "max_refinements BETWEEN 0 AND 10", name="ck_agent_workflow_runs_max_refinements"
        ),
        CheckConstraint("refinement_count >= 0", name="ck_agent_workflow_runs_refinement_count"),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    content_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    brand_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[AgentWorkflowStatus] = mapped_column(
        agent_workflow_status_enum, nullable=False, server_default=text("'PENDING'")
    )
    human_review: Mapped[HumanReviewMode] = mapped_column(
        human_review_mode_enum, nullable=False, server_default=text("'AUTO'")
    )
    max_refinements: Mapped[int] = mapped_column(nullable=False, server_default=text("3"))
    refinement_count: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    current_step: Mapped[str | None] = mapped_column(String(64))
    input_json: Mapped[dict[str, object]] = mapped_column(
        "input", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    final_image_ids: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(
        timestamp_tz, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        timestamp_tz, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[object | None] = mapped_column(timestamp_tz)
    deleted_at: Mapped[object | None] = mapped_column(timestamp_tz)
