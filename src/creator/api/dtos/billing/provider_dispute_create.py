from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProviderDisputeCreateRequest(BaseModel):
    billing_account_id: UUID
    charge_id: UUID | None = None
    code: str | None = None
    reason: str | None = None
    opened_at: datetime | None = None
    deadline_at: datetime | None = None
