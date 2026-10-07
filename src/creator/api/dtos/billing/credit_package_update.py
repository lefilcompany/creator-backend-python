from pydantic import BaseModel


class CreditPackageUpdateRequest(BaseModel):
    name: str | None = None
    credits_amount: int | None = None
    price_cents: int | None = None
    currency: str | None = None
    is_active: bool | None = None
