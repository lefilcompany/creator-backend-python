from pydantic import Field

from ..base import CreatorDTO


class BillingAccountUpdateRequest(CreatorDTO):
    payer_type: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = Field(default=None, min_length=1, max_length=64)
    phone: str | None = Field(default=None, max_length=20)
    document: str | None = Field(default=None, max_length=50)
    document_type: str | None = Field(default=None, max_length=10)
    company_name: str | None = Field(default=None, max_length=64)
