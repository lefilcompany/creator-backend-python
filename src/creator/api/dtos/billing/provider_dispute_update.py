from pydantic import BaseModel


class ProviderDisputeUpdateRequest(BaseModel):
    reason: str | None = None
    status: str | None = None
