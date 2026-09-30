from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class BillingAccountCreateRequest(CreatorDTO):
    user_id: UUID
    payer_type: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=64)
    email: str = Field(min_length=1, max_length=64)
    phone: str | None = Field(default=None, max_length=20)
    document: str | None = Field(default=None, max_length=50)
    document_type: str | None = Field(default=None, max_length=10)
