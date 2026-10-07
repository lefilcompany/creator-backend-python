from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CouponRecord:
    id: UUID
    code: str
    type: str
    discount_percent: float | None
    credits_amount: int | None
    applies_to: str
    min_purchase_cents: int | None
    max_redemptions: int | None
    once_per_workspace: bool
    redemptions_count: int
    expires_at: datetime | None
    is_active: bool
    internal_note: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class CouponRepository(Protocol):
    def list(self) -> list[CouponRecord]: ...
    def get(self, *, coupon_id: UUID) -> CouponRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> CouponRecord: ...
    def update(self, *, coupon_id: UUID, fields: dict[str, object]) -> CouponRecord: ...
    def soft_delete(self, *, coupon_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class CreditPackageRecord:
    id: UUID
    code: str
    name: str
    credits_amount: int
    price_cents: int
    currency: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class CreditPackageRepository(Protocol):
    def list(self) -> list[CreditPackageRecord]: ...
    def get(self, *, package_id: UUID) -> CreditPackageRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> CreditPackageRecord: ...
    def update(self, *, package_id: UUID, fields: dict[str, object]) -> CreditPackageRecord: ...
    def soft_delete(self, *, package_id: UUID) -> None: ...
