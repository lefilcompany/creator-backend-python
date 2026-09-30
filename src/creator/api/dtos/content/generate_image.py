from typing import Literal
from uuid import UUID

from ..base import CreatorDTO


class GenerateImageRequest(CreatorDTO):
    content_id: UUID
    style: Literal["photographic", "illustration", "product_render"] | None = None
