from uuid import UUID

from pydantic import BaseModel


class BrandColorCreateRequest(BaseModel):
    brand_id: UUID
    workspace_id: UUID
    order: int = 0
    color_name: str | None = None
    hex_code: str | None = None
