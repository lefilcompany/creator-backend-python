from uuid import UUID

from pydantic import BaseModel


class PaymentMethodCreateRequest(BaseModel):
    billing_account_id: UUID
    holder_name: str | None = None
    holder_document: str | None = None
    card_brand: str | None = None
    card_last_four: str | None = None
    exp_month: int | None = None
    exp_year: int | None = None
    card_type: str | None = None
    is_default: bool = False
