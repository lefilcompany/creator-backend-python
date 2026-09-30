"""Align core user/workspace string lengths with Creator DB.pdf."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_core_schema_lengths"
down_revision: str | None = "0010_database_diagram_slices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "users", "email", existing_type=sa.String(length=320), type_=sa.String(length=50)
    )
    op.alter_column(
        "users", "display_name", existing_type=sa.String(length=255), type_=sa.String(length=50)
    )
    op.alter_column(
        "workspaces", "name", existing_type=sa.String(length=255), type_=sa.String(length=50)
    )


def downgrade() -> None:
    op.alter_column(
        "workspaces", "name", existing_type=sa.String(length=50), type_=sa.String(length=255)
    )
    op.alter_column(
        "users", "display_name", existing_type=sa.String(length=50), type_=sa.String(length=255)
    )
    op.alter_column(
        "users", "email", existing_type=sa.String(length=50), type_=sa.String(length=320)
    )
