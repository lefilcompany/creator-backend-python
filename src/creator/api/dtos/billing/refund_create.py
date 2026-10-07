from uuid import UUID

from pydantic import BaseModel, Field


class RefundCreateRequest(BaseModel):
    billing_account_id: UUID
    invoice_id: UUID | None = None
    amount_cents: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    reason: str | None = None
