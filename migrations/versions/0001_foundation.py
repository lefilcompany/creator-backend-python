"""Create the initial Creator schema boundary.

Revision ID: 0001_foundation
Revises:
"""

from collections.abc import Sequence

revision: str = "0001_foundation"
down_revision: str | Sequence[str] | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
