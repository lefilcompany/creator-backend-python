from __future__ import annotations

# mypy: disable-error-code=no-untyped-def
# mypy: disallow_untyped_calls=False
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from creator.infrastructure import models, schema_models
from creator.repositories.commerce import (
    CouponRedemptionRecord,
    CouponRedemptionRepository,
    OrderRecord,
    OrderRepository,
    WorkspaceCreditTransactionRecord,
    WorkspaceCreditTransactionRepository,
)


class SqlAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: Session) -> None:
        self.s = session

    def _r(self, x):
        return OrderRecord(
            x.id,
            x.billing_account_id,
            x.workspace_id,
            x.credit_package_id,
            x.subtotal_cents,
            x.discount_cents,
            x.amount_cents,
            x.currency,
            x.status,
            x.closed,
            x.created_at,
            x.updated_at,
            x.deleted_at,
        )

    def _owned(self, uid, oid):
        return self.s.scalar(
            select(schema_models.Order)
            .join(schema_models.BillingAccount)
            .where(
                schema_models.Order.id == oid,
                schema_models.BillingAccount.user_id == uid,
                schema_models.Order.deleted_at.is_(None),
            )
        )

    def list_for_user(self, *, user_id):
        return [
            self._r(x)
            for x in self.s.scalars(
                select(schema_models.Order)
                .join(schema_models.BillingAccount)
                .where(
                    schema_models.BillingAccount.user_id == user_id,
                    schema_models.Order.deleted_at.is_(None),
                )
            ).all()
        ]

    def get_for_user(self, *, user_id, order_id):
        x = self._owned(user_id, order_id)
        return self._r(x) if x else None

    def add(self, *, fields):
        x = schema_models.Order(**fields)
        self.s.add(x)
        self.s.flush()
        return self._r(x)

    def update(self, *, order_id, fields):
        x = self.s.get(schema_models.Order, order_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Order not found")
        for k, v in fields.items():
            setattr(x, k, v)
        x.updated_at = datetime.now(UTC)
        self.s.flush()
        return self._r(x)

    def soft_delete(self, *, order_id):
        x = self.s.get(schema_models.Order, order_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Order not found")
        x.deleted_at = datetime.now(UTC)
        x.updated_at = x.deleted_at
        self.s.flush()


class SqlAlchemyWorkspaceCreditTransactionRepository(WorkspaceCreditTransactionRepository):
    def __init__(self, session: Session) -> None:
        self.s = session

    def _r(self, x: schema_models.WorkspaceCreditTransaction) -> WorkspaceCreditTransactionRecord:
        return WorkspaceCreditTransactionRecord(
            x.id,
            x.workspace_id,
            x.amount,
            x.transaction_type,
            x.reference_type,
            x.reference_id,
            x.created_at,
            x.updated_at,
            x.deleted_at,
        )

    def list_for_user(
        self, *, user_id: UUID, workspace_id: UUID | None = None
    ) -> list[WorkspaceCreditTransactionRecord]:
        q = (
            select(schema_models.WorkspaceCreditTransaction)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id
                == schema_models.WorkspaceCreditTransaction.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.WorkspaceCreditTransaction.deleted_at.is_(None),
            )
        )
        if workspace_id is not None:
            q = q.where(schema_models.WorkspaceCreditTransaction.workspace_id == workspace_id)
        return [self._r(x) for x in self.s.scalars(q).all()]

    def get_for_user(
        self, *, user_id: UUID, transaction_id: UUID
    ) -> WorkspaceCreditTransactionRecord | None:
        x = self.s.scalar(
            select(schema_models.WorkspaceCreditTransaction)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id
                == schema_models.WorkspaceCreditTransaction.workspace_id,
            )
            .where(
                schema_models.WorkspaceCreditTransaction.id == transaction_id,
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.WorkspaceCreditTransaction.deleted_at.is_(None),
            )
        )
        return self._r(x) if x else None

    def add(self, *, fields: dict[str, object]) -> WorkspaceCreditTransactionRecord:
        x = schema_models.WorkspaceCreditTransaction(**fields)
        self.s.add(x)
        self.s.flush()
        return self._r(x)

    def soft_delete(self, *, transaction_id: UUID) -> None:
        x = self.s.get(schema_models.WorkspaceCreditTransaction, transaction_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Workspace credit transaction not found")
        x.deleted_at = datetime.now(UTC)
        x.updated_at = x.deleted_at
        self.s.flush()


class SqlAlchemyCouponRedemptionRepository(CouponRedemptionRepository):
    def __init__(self, session: Session) -> None:
        self.s = session

    def _r(self, x):
        return CouponRedemptionRecord(
            x.id,
            x.coupon_id,
            x.billing_account_id,
            x.order_id,
            x.subscription_id,
            float(x.discount_percent_applied) if x.discount_percent_applied is not None else None,
            x.discount_amount_cents,
            x.credits_applied,
            x.status,
            x.created_at,
            x.updated_at,
            x.deleted_at,
        )

    def _owned(self, uid, rid):
        return self.s.scalar(
            select(schema_models.CouponRedemption)
            .join(schema_models.BillingAccount)
            .where(
                schema_models.CouponRedemption.id == rid,
                schema_models.BillingAccount.user_id == uid,
                schema_models.CouponRedemption.deleted_at.is_(None),
            )
        )

    def list_for_user(self, *, user_id):
        return [
            self._r(x)
            for x in self.s.scalars(
                select(schema_models.CouponRedemption)
                .join(schema_models.BillingAccount)
                .where(
                    schema_models.BillingAccount.user_id == user_id,
                    schema_models.CouponRedemption.deleted_at.is_(None),
                )
            ).all()
        ]

    def get_for_user(self, *, user_id, redemption_id):
        x = self._owned(user_id, redemption_id)
        return self._r(x) if x else None

    def add(self, *, fields):
        x = schema_models.CouponRedemption(**fields)
        self.s.add(x)
        self.s.flush()
        return self._r(x)

    def update(self, *, redemption_id, fields):
        x = self.s.get(schema_models.CouponRedemption, redemption_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Coupon redemption not found")
        for k, v in fields.items():
            setattr(x, k, v)
        x.updated_at = datetime.now(UTC)
        self.s.flush()
        return self._r(x)

    def soft_delete(self, *, redemption_id):
        x = self.s.get(schema_models.CouponRedemption, redemption_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Coupon redemption not found")
        x.deleted_at = datetime.now(UTC)
        x.updated_at = x.deleted_at
        self.s.flush()
