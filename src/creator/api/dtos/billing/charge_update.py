from pydantic import Field

from ..base import CreatorDTO


class ChargeUpdateRequest(CreatorDTO):
    amount_cents: int | None = Field(default=None, ge=0)
