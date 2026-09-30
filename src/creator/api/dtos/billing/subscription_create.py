from datetime import datetime
from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class SubscriptionCreateRequest(CreatorDTO):
    billing_account_id: UUID
    workspace_id: UUID
    plan_id: UUID
    payment_method: str | None = None
    billing_day: int | None = Field(default=None, ge=1, le=31)
    start_at: datetime | None = None
