from pydantic import Field

from ..base import CreatorDTO


class PostStructureUpdateRequest(CreatorDTO):
    title: str | None = Field(default=None, max_length=100)
    objective: str | None = Field(default=None, max_length=300)
    big_idea: str | None = Field(default=None, max_length=150)
    main_message: str | None = Field(default=None, max_length=150)
    headline: str | None = Field(default=None, max_length=50)
    image_cta: str | None = Field(default=None, max_length=30)
    art_guiding: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, max_length=20)
    format: str | None = None
    ratio: str | None = None
    resolution: str | None = None
