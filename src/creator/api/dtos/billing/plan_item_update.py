from pydantic import Field

from ..base import CreatorDTO


class PlanItemUpdateRequest(CreatorDTO):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    quantity: int | None = Field(default=None, ge=1)
    cycles: int | None = Field(default=None, ge=1)
    pricing_scheme_type: str | None = Field(default=None, max_length=20)
    price_cents: int | None = Field(default=None, ge=0)
    price_brackets: dict[str, object] | None = None
    status: str | None = Field(default=None, max_length=20)
