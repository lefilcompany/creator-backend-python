from pydantic import BaseModel, Field


class CreditPackageCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    credits_amount: int = Field(gt=0)
    price_cents: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    is_active: bool = True
