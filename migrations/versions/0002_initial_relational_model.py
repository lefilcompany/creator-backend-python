"""Create the initial relational Creator model.

Revision ID: 0002_initial_relational_model
Revises: 0001_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_initial_relational_model"
down_revision: str | Sequence[str] | None = "0001_foundation"
branch_labels = None
depends_on = None


GLOBAL_ROLE = postgresql.ENUM(
    "admin",
    "gestor",
    "membro",
    name="global_role",
    create_type=False,
)
WORKSPACE_ROLE = postgresql.ENUM(
    "owner",
    "admin",
    "editor",
    "viewer",
    name="workspace_role",
    create_type=False,
)
CONTENT_TYPE = postgresql.ENUM("IMAGE", name="content_type", create_type=False)
GENERATION_TYPE = postgresql.ENUM("IMAGE", name="generation_type", create_type=False)
GENERATION_JOB_STATUS = postgresql.ENUM(
    "PENDING",
    "PROCESSING",
    "COMPLETED",
    "FAILED",
    name="generation_job_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))

    postgresql.ENUM("admin", "gestor", "membro", name="global_role").create(
        bind,
        checkfirst=True,
    )
    postgresql.ENUM("owner", "admin", "editor", "viewer", name="workspace_role").create(
        bind,
        checkfirst=True,
    )
    postgresql.ENUM("IMAGE", name="content_type").create(bind, checkfirst=True)
    postgresql.ENUM("IMAGE", name="generation_type").create(bind, checkfirst=True)
    postgresql.ENUM(
        "PENDING",
        "PROCESSING",
        "COMPLETED",
        "FAILED",
        name="generation_job_status",
    ).create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("auth_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("global_role", GLOBAL_ROLE, server_default=sa.text("'membro'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("auth_subject", name="uq_users_auth_subject"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])

    op.create_table(
        "settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_settings_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_settings")),
        sa.UniqueConstraint("user_id", name="uq_settings_user_id"),
    )
    op.create_index("ix_settings_user_id", "settings", ["user_id"])

    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
    )
    op.create_index("ix_workspaces_deleted_at", "workspaces", ["deleted_at"])

    op.create_table(
        "workspace_memberships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", WORKSPACE_ROLE, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_memberships_deleted_after_created",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_workspace_memberships_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_workspace_memberships_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_memberships")),
    )
    op.create_index(
        "ix_workspace_memberships_user_id",
        "workspace_memberships",
        ["user_id"],
    )
    op.create_index(
        "ix_workspace_memberships_workspace_id",
        "workspace_memberships",
        ["workspace_id"],
    )
    op.create_index(
        "uq_workspace_memberships_active_user_workspace",
        "workspace_memberships",
        ["user_id", "workspace_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "contents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type", CONTENT_TYPE, server_default=sa.text("'IMAGE'"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_contents_deleted_after_created",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_contents_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_contents_workspace_id_workspaces"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contents")),
        sa.UniqueConstraint("id", "workspace_id", name="uq_contents_id_workspace_id"),
    )
    op.create_index("ix_contents_created_by_user_id", "contents", ["created_by_user_id"])
    op.create_index(
        "ix_contents_workspace_filter",
        "contents",
        ["workspace_id", "type", "deleted_at", "created_at"],
    )

    op.create_table(
        "generations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type", GENERATION_TYPE, server_default=sa.text("'IMAGE'"), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column(
            "parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(prompt) BETWEEN 1 AND 20000",
            name="ck_generations_prompt_length",
        ),
        sa.CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_generations_deleted_after_created",
        ),
        sa.ForeignKeyConstraint(
            ["content_id", "workspace_id"],
            ["contents.id", "contents.workspace_id"],
            name="fk_generations_content_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_generations_requested_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_generations_workspace_id_workspaces"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generations")),
        sa.UniqueConstraint("id", "workspace_id", name="uq_generations_id_workspace_id"),
        sa.UniqueConstraint(
            "id",
            "workspace_id",
            "content_id",
            name="uq_generations_id_workspace_content_id",
        ),
    )
    op.create_index("ix_generations_requested_by_user_id", "generations", ["requested_by_user_id"])
    op.create_index(
        "ix_generations_workspace_filter",
        "generations",
        ["workspace_id", "type", "deleted_at", "created_at"],
    )

    op.create_table(
        "generation_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status", GENERATION_JOB_STATUS, server_default=sa.text("'PENDING'"), nullable=False
        ),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column(
            "queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "attempt_count >= 0", name="ck_generation_jobs_attempt_count_non_negative"
        ),
        sa.CheckConstraint("max_attempts > 0", name="ck_generation_jobs_max_attempts_positive"),
        sa.CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_generation_jobs_deleted_after_created",
        ),
        sa.ForeignKeyConstraint(
            ["generation_id", "workspace_id"],
            ["generations.id", "generations.workspace_id"],
            name="fk_generation_jobs_generation_workspace",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generation_jobs")),
    )
    op.create_index("ix_generation_jobs_generation_id", "generation_jobs", ["generation_id"])
    op.create_index(
        "ix_generation_jobs_status_created_at",
        "generation_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_generation_jobs_workspace_status_created_at",
        "generation_jobs",
        ["workspace_id", "status", "created_at"],
    )
    op.create_index(
        "uq_generation_jobs_external_id",
        "generation_jobs",
        ["external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "generation_job_status_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("generation_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_status", GENERATION_JOB_STATUS, nullable=True),
        sa.Column("status", GENERATION_JOB_STATUS, nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "previous_status IS NULL OR previous_status <> status",
            name="ck_generation_job_status_events_status_changed",
        ),
        sa.ForeignKeyConstraint(
            ["generation_job_id"],
            ["generation_jobs.id"],
            name=op.f("fk_generation_job_status_events_generation_job_id_generation_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generation_job_status_events")),
    )
    op.create_index(
        "ix_generation_job_status_events_job_occurred_at",
        "generation_job_status_events",
        ["generation_job_id", "occurred_at"],
    )

    op.create_table(
        "images",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("public_url", sa.String(length=2048), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version_number > 0", name="ck_images_version_number_positive"),
        sa.CheckConstraint(
            "mime_type IN ('image/png', 'image/jpeg', 'image/webp')",
            name="ck_images_mime_type_supported",
        ),
        sa.CheckConstraint("width > 0", name="ck_images_width_positive"),
        sa.CheckConstraint("height > 0", name="ck_images_height_positive"),
        sa.CheckConstraint(
            "char_length(prompt) BETWEEN 1 AND 20000", name="ck_images_prompt_length"
        ),
        sa.CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_images_deleted_after_created",
        ),
        sa.ForeignKeyConstraint(
            ["content_id", "workspace_id"],
            ["contents.id", "contents.workspace_id"],
            name="fk_images_content_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["generation_id", "workspace_id", "content_id"],
            ["generations.id", "generations.workspace_id", "generations.content_id"],
            name="fk_images_generation_workspace_content",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_images_workspace_id_workspaces"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_images")),
        sa.UniqueConstraint("generation_id", name="uq_images_generation_id"),
        sa.UniqueConstraint("storage_path", name="uq_images_storage_path"),
    )
    op.create_index("ix_images_content_version", "images", ["content_id", "version_number"])
    op.create_index(
        "ix_images_workspace_filter", "images", ["workspace_id", "deleted_at", "created_at"]
    )
    op.create_index(
        "uq_images_active_content_version",
        "images",
        ["content_id", "version_number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("uq_images_active_content_version", table_name="images")
    op.drop_index("ix_images_workspace_filter", table_name="images")
    op.drop_index("ix_images_content_version", table_name="images")
    op.drop_table("images")

    op.drop_index(
        "ix_generation_job_status_events_job_occurred_at",
        table_name="generation_job_status_events",
    )
    op.drop_table("generation_job_status_events")

    op.drop_index("uq_generation_jobs_external_id", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_workspace_status_created_at", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_status_created_at", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_generation_id", table_name="generation_jobs")
    op.drop_table("generation_jobs")

    op.drop_index("ix_generations_workspace_filter", table_name="generations")
    op.drop_index("ix_generations_requested_by_user_id", table_name="generations")
    op.drop_table("generations")

    op.drop_index("ix_contents_workspace_filter", table_name="contents")
    op.drop_index("ix_contents_created_by_user_id", table_name="contents")
    op.drop_table("contents")

    op.drop_index(
        "uq_workspace_memberships_active_user_workspace",
        table_name="workspace_memberships",
    )
    op.drop_index("ix_workspace_memberships_workspace_id", table_name="workspace_memberships")
    op.drop_index("ix_workspace_memberships_user_id", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")

    op.drop_index("ix_workspaces_deleted_at", table_name="workspaces")
    op.drop_table("workspaces")

    op.drop_index("ix_settings_user_id", table_name="settings")
    op.drop_table("settings")

    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_table("users")

    postgresql.ENUM(name="generation_job_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="generation_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="content_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="workspace_role").drop(bind, checkfirst=True)
    postgresql.ENUM(name="global_role").drop(bind, checkfirst=True)
