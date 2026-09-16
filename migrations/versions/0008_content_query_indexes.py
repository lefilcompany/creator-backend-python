"""Add Content query indexes.

Revision ID: 0008_content_query_indexes
Revises: 0007_user_brand_settings
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_content_query_indexes"
down_revision: str | Sequence[str] | None = "0007_user_brand_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_contents_workspace_created_id",
        "contents",
        ["workspace_id", "deleted_at", "created_at", "id"],
    )
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX ix_contents_search_trgm
        ON contents
        USING gin ((lower(coalesce(title, '') || ' ' || payload::text)) gin_trgm_ops)
        WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_contents_search_trgm")
    op.drop_index("ix_contents_workspace_created_id", table_name="contents")
