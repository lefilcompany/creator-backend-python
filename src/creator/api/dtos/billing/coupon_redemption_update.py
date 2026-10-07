from pydantic import BaseModel


class CouponRedemptionUpdateRequest(BaseModel):
    status: str | None = None
