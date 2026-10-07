from pydantic import BaseModel


class OrderUpdateRequest(BaseModel):
    status: str | None = None
    closed: bool | None = None
