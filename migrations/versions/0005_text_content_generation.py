"""Add text Content and Generation types.

Revision ID: 0005_text_content_generation
Revises: 0004_image_metadata
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_text_content_generation"
down_revision: str | Sequence[str] | None = "0004_image_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE content_type ADD VALUE IF NOT EXISTS 'TEXT'"))
    op.execute(sa.text("ALTER TYPE generation_type ADD VALUE IF NOT EXISTS 'TEXT'"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM generations WHERE type = 'TEXT'"))
    bind.execute(sa.text("DELETE FROM contents WHERE type = 'TEXT'"))

    bind.execute(sa.text("ALTER TYPE content_type RENAME TO content_type_with_text"))
    bind.execute(sa.text("CREATE TYPE content_type AS ENUM ('IMAGE')"))
    bind.execute(sa.text("ALTER TABLE contents ALTER COLUMN type DROP DEFAULT"))
    bind.execute(
        sa.text(
            "ALTER TABLE contents ALTER COLUMN type TYPE content_type "
            "USING type::text::content_type"
        )
    )
    bind.execute(sa.text("ALTER TABLE contents ALTER COLUMN type SET DEFAULT 'IMAGE'"))
    bind.execute(sa.text("DROP TYPE content_type_with_text"))

    bind.execute(sa.text("ALTER TYPE generation_type RENAME TO generation_type_with_text"))
    bind.execute(sa.text("CREATE TYPE generation_type AS ENUM ('IMAGE')"))
    bind.execute(sa.text("ALTER TABLE generations ALTER COLUMN type DROP DEFAULT"))
    bind.execute(
        sa.text(
            "ALTER TABLE generations ALTER COLUMN type TYPE generation_type "
            "USING type::text::generation_type"
        )
    )
    bind.execute(sa.text("ALTER TABLE generations ALTER COLUMN type SET DEFAULT 'IMAGE'"))
    bind.execute(sa.text("DROP TYPE generation_type_with_text"))
