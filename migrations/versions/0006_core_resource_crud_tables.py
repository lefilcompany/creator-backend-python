"""Add core resource CRUD tables.

Revision ID: 0006_core_resource_crud_tables
Revises: 0005_text_content_generation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_core_resource_crud_tables"
down_revision: str | Sequence[str] | None = "0005_text_content_generation"
branch_labels = None
depends_on = None


def uuid_column() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "brands",
        uuid_column(),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("brand_voice", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *timestamps(),
        sa.CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_brands_deleted_after_created",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_brands_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_brands_workspace_id_workspaces"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brands")),
        sa.UniqueConstraint("id", "workspace_id", name="uq_brands_id_workspace_id"),
    )
    op.create_index("ix_brands_created_by_user_id", "brands", ["created_by_user_id"])
    op.create_index(
        "ix_brands_workspace_filter", "brands", ["workspace_id", "deleted_at", "created_at"]
    )

    op.create_table(
        "brand_settings",
        uuid_column(),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "voice_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "visual_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "generation_defaults",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *timestamps(),
        sa.CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_brand_settings_deleted_after_created",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id", "workspace_id"],
            ["brands.id", "brands.workspace_id"],
            name="fk_brand_settings_brand_workspace",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_brand_settings_workspace_id_workspaces"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brand_settings")),
        sa.UniqueConstraint("brand_id", name="uq_brand_settings_brand_id"),
    )
    op.create_index("ix_brand_settings_workspace_id", "brand_settings", ["workspace_id"])

    op.create_table(
        "projects",
        uuid_column(),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="ck_projects_status_valid"),
        sa.CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_projects_deleted_after_created",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id", "workspace_id"],
            ["brands.id", "brands.workspace_id"],
            name="fk_projects_brand_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_projects_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_projects_workspace_id_workspaces"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.UniqueConstraint("id", "workspace_id", name="uq_projects_id_workspace_id"),
    )
    op.create_index("ix_projects_brand_id", "projects", ["brand_id"])
    op.create_index("ix_projects_created_by_user_id", "projects", ["created_by_user_id"])
    op.create_index(
        "ix_projects_workspace_filter", "projects", ["workspace_id", "deleted_at", "created_at"]
    )

    op.add_column("contents", sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("contents", sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_contents_brand_workspace",
        "contents",
        "brands",
        ["brand_id", "workspace_id"],
        ["id", "workspace_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_contents_project_workspace",
        "contents",
        "projects",
        ["project_id", "workspace_id"],
        ["id", "workspace_id"],
        ondelete="RESTRICT",
    )

    op.add_column("generations", sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "generations", sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_generations_brand_workspace",
        "generations",
        "brands",
        ["brand_id", "workspace_id"],
        ["id", "workspace_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_generations_project_workspace",
        "generations",
        "projects",
        ["project_id", "workspace_id"],
        ["id", "workspace_id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "assets",
        uuid_column(),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_type", sa.String(length=100), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("public_url", sa.String(length=2048), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=255), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *timestamps(),
        sa.CheckConstraint("byte_size >= 0", name="ck_assets_byte_size_non_negative"),
        sa.CheckConstraint("char_length(asset_type) BETWEEN 1 AND 100", name="ck_assets_type_length"),
        sa.CheckConstraint(
            "deleted_at IS NULL OR deleted_at >= created_at",
            name="ck_assets_deleted_after_created",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id", "workspace_id"],
            ["brands.id", "brands.workspace_id"],
            name="fk_assets_brand_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["content_id", "workspace_id"],
            ["contents.id", "contents.workspace_id"],
            name="fk_assets_content_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "workspace_id"],
            ["projects.id", "projects.workspace_id"],
            name="fk_assets_project_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            name=op.f("fk_assets_uploaded_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_assets_workspace_id_workspaces"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
        sa.UniqueConstraint("storage_path", name="uq_assets_storage_path"),
    )
    op.create_index("ix_assets_brand_id", "assets", ["brand_id"])
    op.create_index("ix_assets_content_id", "assets", ["content_id"])
    op.create_index("ix_assets_project_id", "assets", ["project_id"])
    op.create_index(
        "ix_assets_workspace_filter", "assets", ["workspace_id", "deleted_at", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_assets_workspace_filter", table_name="assets")
    op.drop_index("ix_assets_project_id", table_name="assets")
    op.drop_index("ix_assets_content_id", table_name="assets")
    op.drop_index("ix_assets_brand_id", table_name="assets")
    op.drop_table("assets")

    op.drop_constraint("fk_generations_project_workspace", "generations", type_="foreignkey")
    op.drop_constraint("fk_generations_brand_workspace", "generations", type_="foreignkey")
    op.drop_column("generations", "project_id")
    op.drop_column("generations", "brand_id")

    op.drop_constraint("fk_contents_project_workspace", "contents", type_="foreignkey")
    op.drop_constraint("fk_contents_brand_workspace", "contents", type_="foreignkey")
    op.drop_column("contents", "project_id")
    op.drop_column("contents", "brand_id")

    op.drop_index("ix_projects_workspace_filter", table_name="projects")
    op.drop_index("ix_projects_created_by_user_id", table_name="projects")
    op.drop_index("ix_projects_brand_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_brand_settings_workspace_id", table_name="brand_settings")
    op.drop_table("brand_settings")

    op.drop_index("ix_brands_workspace_filter", table_name="brands")
    op.drop_index("ix_brands_created_by_user_id", table_name="brands")
    op.drop_table("brands")
