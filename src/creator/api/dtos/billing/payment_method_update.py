from pydantic import BaseModel


class PaymentMethodUpdateRequest(BaseModel):
    holder_name: str | None = None
    holder_document: str | None = None
    is_default: bool | None = None
