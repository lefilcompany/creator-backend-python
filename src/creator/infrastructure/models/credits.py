from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from creator.infrastructure.db import Base

from .types import timestamp_tz, uuid_pk


class CreditWallet(Base):
    __tablename__ = "credit_wallets"
    __table_args__ = (
        UniqueConstraint("workspace_id", name="uq_credit_wallets_workspace_id"),
        CheckConstraint("balance >= 0", name="ck_credit_wallets_balance_nonnegative"),
        CheckConstraint("monthly_allowance >= 0", name="ck_credit_wallets_allowance_nonnegative"),
        CheckConstraint("purchased_credits >= 0", name="ck_credit_wallets_purchased_nonnegative"),
        CheckConstraint("total_spent >= 0", name="ck_credit_wallets_spent_nonnegative"),
        Index("ix_credit_wallets_workspace_id", "workspace_id"),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    monthly_allowance: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    purchased_credits: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_spent: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cycle_started_at: Mapped[object] = mapped_column(
        timestamp_tz, nullable=False, server_default=func.now()
    )
    created_at: Mapped[object] = mapped_column(
        timestamp_tz, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        timestamp_tz, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "idempotency_key", name="uq_credit_transactions_workspace_idempotency"
        ),
        CheckConstraint("credits <> 0", name="ck_credit_transactions_credits_nonzero"),
        CheckConstraint("quantity > 0", name="ck_credit_transactions_quantity_positive"),
        Index("ix_credit_transactions_workspace_created_at", "workspace_id", "created_at"),
        Index("ix_credit_transactions_workspace_action", "workspace_id", "action_key"),
        Index("ix_credit_transactions_workspace_user", "workspace_id", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action_key: Mapped[str] = mapped_column(String(100), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[object] = mapped_column(
        timestamp_tz, nullable=False, server_default=func.now()
    )


class CreditPrice(Base):
    __tablename__ = "credit_prices"
    __table_args__ = (
        UniqueConstraint("action_key", name="uq_credit_prices_action_key"),
        CheckConstraint("credits > 0", name="ck_credit_prices_credits_positive"),
        Index("ix_credit_prices_action_active", "action_key", "active"),
    )

    id: Mapped[UUID] = mapped_column(
        uuid_pk, primary_key=True, server_default=text("gen_random_uuid()")
    )
    action_key: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
