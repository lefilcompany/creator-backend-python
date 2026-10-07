from datetime import datetime

from pydantic import BaseModel, Field


class CouponCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    type: str
    applies_to: str
    discount_percent: float | None = None
    credits_amount: int | None = None
    min_purchase_cents: int | None = None
    max_redemptions: int | None = None
    once_per_workspace: bool = False
    expires_at: datetime | None = None
    is_active: bool = True
    internal_note: str | None = None
