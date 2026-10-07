from pydantic import BaseModel


class RefundUpdateRequest(BaseModel):
    reason: str | None = None
    status: str | None = None
