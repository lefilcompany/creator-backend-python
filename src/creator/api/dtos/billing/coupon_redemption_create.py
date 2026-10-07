from uuid import UUID

from pydantic import BaseModel


class CouponRedemptionCreateRequest(BaseModel):
    coupon_id: UUID
    billing_account_id: UUID
    order_id: UUID | None = None
    subscription_id: UUID | None = None
    discount_percent_applied: float | None = None
    discount_amount_cents: int | None = None
    credits_applied: int | None = None
