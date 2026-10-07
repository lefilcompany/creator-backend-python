from uuid import UUID

from pydantic import BaseModel


class ProviderCustomerCreateRequest(BaseModel):
    billing_account_id: UUID
    provider: str
    provider_customer_id: str
    provider_code: str | None = None
    metadata: dict[str, object] = {}
