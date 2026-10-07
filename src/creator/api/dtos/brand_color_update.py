from pydantic import BaseModel


class BrandColorUpdateRequest(BaseModel):
    order: int | None = None
    color_name: str | None = None
    hex_code: str | None = None
