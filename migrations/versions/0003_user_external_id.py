"""Rename user external identity column.

Revision ID: 0003_user_external_id
Revises: 0002_initial_relational_model
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_user_external_id"
down_revision: str | Sequence[str] | None = "0002_initial_relational_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_users_auth_subject", "users", type_="unique")
    op.alter_column("users", "auth_subject", new_column_name="external_id")
    op.create_unique_constraint("uq_users_external_id", "users", ["external_id"])


def downgrade() -> None:
    op.drop_constraint("uq_users_external_id", "users", type_="unique")
    op.alter_column("users", "external_id", new_column_name="auth_subject")
    op.create_unique_constraint("uq_users_auth_subject", "users", ["auth_subject"])

