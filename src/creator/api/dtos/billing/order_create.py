from uuid import UUID

from pydantic import BaseModel, Field


class OrderCreateRequest(BaseModel):
    billing_account_id: UUID
    workspace_id: UUID
    credit_package_id: UUID | None = None
    subtotal_cents: int = Field(ge=0)
    discount_cents: int = Field(default=0, ge=0)
    amount_cents: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
