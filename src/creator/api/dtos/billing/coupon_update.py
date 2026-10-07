from datetime import datetime

from pydantic import BaseModel


class CouponUpdateRequest(BaseModel):
    type: str | None = None
    applies_to: str | None = None
    discount_percent: float | None = None
    credits_amount: int | None = None
    min_purchase_cents: int | None = None
    max_redemptions: int | None = None
    once_per_workspace: bool | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None
    internal_note: str | None = None
