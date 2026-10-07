from pydantic import BaseModel


class BillingAddressUpdateRequest(BaseModel):
    street: str | None = None
    number: str | None = None
    complement: str | None = None
    neighborhood: str | None = None
    zip_code: str | None = None
    city: str | None = None
    state: str | None = None
