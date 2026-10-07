from datetime import datetime

from pydantic import Field

from ..base import CreatorDTO


class SubscriptionUpdateRequest(CreatorDTO):
    payment_method: str | None = None
    billing_day: int | None = Field(default=None, ge=1, le=31)
    start_at: datetime | None = None
