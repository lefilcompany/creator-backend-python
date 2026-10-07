from __future__ import annotations

# mypy: disable-error-code=no-untyped-def
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from creator.infrastructure import schema_models
from creator.repositories.catalog import (
    CouponRecord,
    CouponRepository,
    CreditPackageRecord,
    CreditPackageRepository,
)


class SqlAlchemyCouponRepository(CouponRepository):
    def __init__(self, session: Session) -> None:
        self.s = session

    def _r(self, x: schema_models.Coupon) -> CouponRecord:
        return CouponRecord(
            x.id,
            x.code,
            x.type,
            float(x.discount_percent) if x.discount_percent is not None else None,
            x.credits_amount,
            x.applies_to,
            x.min_purchase_cents,
            x.max_redemptions,
            x.once_per_workspace,
            x.redemptions_count,
            x.expires_at,
            x.is_active,
            x.internal_note,
            x.created_by,
            x.created_at,
            x.updated_at,
            x.deleted_at,
        )

    def list(self):
        return [
            self._r(x)
            for x in self.s.scalars(
                select(schema_models.Coupon).where(schema_models.Coupon.deleted_at.is_(None))
            ).all()
        ]

    def get(self, *, coupon_id: UUID):
        x = self.s.scalar(
            select(schema_models.Coupon).where(
                schema_models.Coupon.id == coupon_id, schema_models.Coupon.deleted_at.is_(None)
            )
        )
        return self._r(x) if x else None

    def add(self, *, fields):
        x = schema_models.Coupon(**fields)
        self.s.add(x)
        self.s.flush()
        return self._r(x)

    def update(self, *, coupon_id: UUID, fields):
        x = self.s.get(schema_models.Coupon, coupon_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Coupon not found")
        for k, v in fields.items():
            setattr(x, k, v)
        x.updated_at = datetime.now(UTC)
        self.s.flush()
        return self._r(x)

    def soft_delete(self, *, coupon_id: UUID):
        x = self.s.get(schema_models.Coupon, coupon_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Coupon not found")
        x.deleted_at = datetime.now(UTC)
        x.updated_at = x.deleted_at
        self.s.flush()


class SqlAlchemyCreditPackageRepository(CreditPackageRepository):
    def __init__(self, session: Session) -> None:
        self.s = session

    def _r(self, x: schema_models.CreditPackage) -> CreditPackageRecord:
        return CreditPackageRecord(
            x.id,
            x.code,
            x.name,
            x.credits_amount,
            x.price_cents,
            x.currency,
            x.is_active,
            x.created_at,
            x.updated_at,
            x.deleted_at,
        )

    def list(self):
        return [
            self._r(x)
            for x in self.s.scalars(
                select(schema_models.CreditPackage).where(
                    schema_models.CreditPackage.deleted_at.is_(None)
                )
            ).all()
        ]

    def get(self, *, package_id: UUID):
        x = self.s.scalar(
            select(schema_models.CreditPackage).where(
                schema_models.CreditPackage.id == package_id,
                schema_models.CreditPackage.deleted_at.is_(None),
            )
        )
        return self._r(x) if x else None

    def add(self, *, fields):
        x = schema_models.CreditPackage(**fields)
        self.s.add(x)
        self.s.flush()
        return self._r(x)

    def update(self, *, package_id: UUID, fields):
        x = self.s.get(schema_models.CreditPackage, package_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Credit package not found")
        for k, v in fields.items():
            setattr(x, k, v)
        x.updated_at = datetime.now(UTC)
        self.s.flush()
        return self._r(x)

    def soft_delete(self, *, package_id: UUID):
        x = self.s.get(schema_models.CreditPackage, package_id)
        if x is None or x.deleted_at is not None:
            raise ValueError("Credit package not found")
        x.deleted_at = datetime.now(UTC)
        x.updated_at = x.deleted_at
        self.s.flush()
