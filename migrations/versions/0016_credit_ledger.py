"""Add workspace credit wallets, append-only transactions, and prices."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0016_credit_ledger"
down_revision: str | Sequence[str] | None = "0015_pipeline_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_wallets",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("balance", sa.Integer(), server_default="0", nullable=False),
        sa.Column("monthly_allowance", sa.Integer(), server_default="0", nullable=False),
        sa.Column("purchased_credits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_spent", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "cycle_started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_credit_wallets_workspace_id"),
        sa.CheckConstraint("balance >= 0", name="ck_credit_wallets_balance_nonnegative"),
        sa.CheckConstraint(
            "monthly_allowance >= 0", name="ck_credit_wallets_allowance_nonnegative"
        ),
        sa.CheckConstraint(
            "purchased_credits >= 0", name="ck_credit_wallets_purchased_nonnegative"
        ),
        sa.CheckConstraint("total_spent >= 0", name="ck_credit_wallets_spent_nonnegative"),
    )
    op.create_index("ix_credit_wallets_workspace_id", "credit_wallets", ["workspace_id"])
    op.create_table(
        "credit_prices",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("action_key", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("action_key", name="uq_credit_prices_action_key"),
        sa.CheckConstraint("credits > 0", name="ck_credit_prices_credits_positive"),
    )
    op.create_index("ix_credit_prices_action_active", "credit_prices", ["action_key", "active"])
    op.create_table(
        "credit_transactions",
        sa.Column(
            "id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action_key", sa.String(100), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(255)),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_credit_transactions_workspace_idempotency"
        ),
        sa.CheckConstraint("credits <> 0", name="ck_credit_transactions_credits_nonzero"),
        sa.CheckConstraint("quantity > 0", name="ck_credit_transactions_quantity_positive"),
    )
    op.create_index(
        "ix_credit_transactions_workspace_created_at",
        "credit_transactions",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_credit_transactions_workspace_action",
        "credit_transactions",
        ["workspace_id", "action_key"],
    )
    op.create_index(
        "ix_credit_transactions_workspace_user", "credit_transactions", ["workspace_id", "user_id"]
    )


def downgrade() -> None:
    for index in (
        "ix_credit_transactions_workspace_user",
        "ix_credit_transactions_workspace_action",
        "ix_credit_transactions_workspace_created_at",
    ):
        op.drop_index(index, table_name="credit_transactions")
    op.drop_table("credit_transactions")
    op.drop_index("ix_credit_prices_action_active", table_name="credit_prices")
    op.drop_table("credit_prices")
    op.drop_index("ix_credit_wallets_workspace_id", table_name="credit_wallets")
    op.drop_table("credit_wallets")
