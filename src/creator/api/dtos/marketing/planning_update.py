from datetime import datetime

from pydantic import Field

from ..base import CreatorDTO


class PlanningUpdateRequest(CreatorDTO):
    info: str | None = Field(default=None, max_length=400)
    static_amount: int | None = Field(default=None, ge=0)
    carousel_amount: int | None = Field(default=None, ge=0)
    stories_amount: int | None = Field(default=None, ge=0)
    special_dates: str | None = Field(default=None, max_length=50)
    start_period: datetime | None = None
    end_period: datetime | None = None
