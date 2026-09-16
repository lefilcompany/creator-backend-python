"""Add Workspace-scoped specialist-agent image workflows.

Revision ID: 0009_agent_image_workflows
Revises: 0008_content_query_indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0009_agent_image_workflows"
down_revision: str | Sequence[str] | None = "0008_content_query_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    agent_workflow_status = sa.Enum(
        "PENDING",
        "RUNNING",
        "WAITING_FOR_HUMAN_REVIEW",
        "REFINING",
        "COMPLETED",
        "REJECTED",
        "FAILED",
        name="agent_workflow_status",
    )
    agent_workflow_step_status = sa.Enum(
        "PENDING", "RUNNING", "COMPLETED", "FAILED", name="agent_workflow_step_status"
    )
    agent_workflow_step_role = sa.Enum(
        "BUSINESS",
        "PLANNER",
        "WRITER",
        "ARTIST",
        "REVIEWER",
        "DELIVERY",
        name="agent_workflow_step_role",
    )
    human_review_mode = sa.Enum("AUTO", "OPTIONAL", name="human_review_mode")
    bind = op.get_bind()
    agent_workflow_status.create(bind, checkfirst=True)
    agent_workflow_step_status.create(bind, checkfirst=True)
    agent_workflow_step_role.create(bind, checkfirst=True)
    human_review_mode.create(bind, checkfirst=True)

    op.create_table(
        "agent_workflow_runs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("content_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", agent_workflow_status, server_default="PENDING", nullable=False),
        sa.Column("human_review", human_review_mode, server_default="AUTO", nullable=False),
        sa.Column("max_refinements", sa.Integer(), server_default="3", nullable=False),
        sa.Column("refinement_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("current_step", sa.String(length=64), nullable=True),
        sa.Column(
            "input",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "final_image_ids",
            JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["content_id", "workspace_id"],
            ["contents.id", "contents.workspace_id"],
            ondelete="RESTRICT",
            name="fk_agent_workflow_runs_content_workspace",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id", "workspace_id"],
            ["brands.id", "brands.workspace_id"],
            ondelete="RESTRICT",
            name="fk_agent_workflow_runs_brand_workspace",
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_agent_workflow_runs_workspace_idempotency_key",
        ),
        sa.CheckConstraint(
            "max_refinements BETWEEN 0 AND 10", name="ck_agent_workflow_runs_max_refinements"
        ),
        sa.CheckConstraint("refinement_count >= 0", name="ck_agent_workflow_runs_refinement_count"),
    )
    op.create_index(
        "ix_agent_workflow_runs_workspace_status_created",
        "agent_workflow_runs",
        ["workspace_id", "status", "created_at"],
    )

    op.create_table(
        "agent_workflow_steps",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("role", agent_workflow_step_role, nullable=False),
        sa.Column("status", agent_workflow_step_status, server_default="PENDING", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "input",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "output",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("prompt_template_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_template_version", sa.String(length=32), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["run_id", "workspace_id"],
            ["agent_workflow_runs.id", "agent_workflow_runs.workspace_id"],
            ondelete="CASCADE",
            name="fk_agent_workflow_steps_run_workspace",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "sequence_number", "attempt", name="uq_agent_workflow_steps_attempt"
        ),
    )
    op.create_index(
        "ix_agent_workflow_steps_run_sequence",
        "agent_workflow_steps",
        ["run_id", "sequence_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_workflow_steps_run_sequence", table_name="agent_workflow_steps")
    op.drop_table("agent_workflow_steps")
    op.drop_index(
        "ix_agent_workflow_runs_workspace_status_created", table_name="agent_workflow_runs"
    )
    op.drop_table("agent_workflow_runs")
    bind = op.get_bind()
    for enum_name in (
        "human_review_mode",
        "agent_workflow_step_role",
        "agent_workflow_step_status",
        "agent_workflow_status",
    ):
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)
