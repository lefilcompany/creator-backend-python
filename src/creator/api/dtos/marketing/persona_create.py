from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class PersonaCreateRequest(CreatorDTO):
    brand_id: UUID
    name: str = Field(min_length=1, max_length=30)
    age: int | None = Field(default=None, ge=0, le=150)
    gender: str | None = Field(default=None, max_length=10)
    main_goal: str | None = Field(default=None, max_length=60)
    challenge: str | None = Field(default=None, max_length=50)
    interest: str | None = Field(default=None, max_length=200)
    routine: str | None = Field(default=None, max_length=300)
    journey: str | None = Field(default=None, max_length=250)
    trigger: str | None = Field(default=None, max_length=200)
