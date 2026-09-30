from datetime import datetime
from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class InvoiceCreateRequest(CreatorDTO):
    billing_account_id: UUID
    subscription_id: UUID | None = None
    amount_cents: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    billing_at: datetime | None = None
    due_at: datetime | None = None
