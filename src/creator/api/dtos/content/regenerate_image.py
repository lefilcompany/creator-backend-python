from typing import Literal

from ..base import CreatorDTO


class RegenerateImageRequest(CreatorDTO):
    style: Literal["photographic", "illustration", "product_render"] | None = None
