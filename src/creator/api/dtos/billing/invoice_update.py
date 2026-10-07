from datetime import datetime

from pydantic import Field

from ..base import CreatorDTO


class InvoiceUpdateRequest(CreatorDTO):
    billing_at: datetime | None = None
    due_at: datetime | None = None
    amount_cents: int | None = Field(default=None, ge=0)
