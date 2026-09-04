"""Align user Settings with brand preference contract.

Revision ID: 0007_user_brand_settings_contract
Revises: 0006_core_resource_crud_tables
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_user_brand_settings_contract"
down_revision: str | Sequence[str] | None = "0006_core_resource_crud_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("brand_name", sa.String(length=255), nullable=True))
    op.add_column("settings", sa.Column("segment", sa.String(length=255), nullable=True))
    op.add_column(
        "settings",
        sa.Column(
            "tone",
            sa.String(length=32),
            server_default=sa.text("'professional'"),
            nullable=False,
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "voice",
            sa.Text(),
            server_default=sa.text("'Clear and useful'"),
            nullable=False,
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "visual_style",
            sa.String(length=32),
            server_default=sa.text("'photographic'"),
            nullable=False,
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "default_preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE settings
        SET default_preferences = preferences
        WHERE preferences <> '{}'::jsonb
        """
    )
    op.drop_column("settings", "preferences")


def downgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE settings
        SET preferences = default_preferences
        WHERE default_preferences <> '{}'::jsonb
        """
    )
    op.drop_column("settings", "default_preferences")
    op.drop_column("settings", "visual_style")
    op.drop_column("settings", "voice")
    op.drop_column("settings", "tone")
    op.drop_column("settings", "segment")
    op.drop_column("settings", "brand_name")
