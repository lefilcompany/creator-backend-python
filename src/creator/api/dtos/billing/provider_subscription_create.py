from uuid import UUID

from pydantic import BaseModel


class ProviderSubscriptionCreateRequest(BaseModel):
    subscription_id: UUID
    provider: str
    provider_subscription_id: str
    provider_status: str | None = None
    payload: dict[str, object] = {}
