from datetime import datetime

from pydantic import Field

from ..base import CreatorDTO


class CampaignUpdateRequest(CreatorDTO):
    name: str | None = Field(default=None, min_length=1, max_length=30)
    description: str | None = Field(default=None, max_length=500)
    target_audience: str | None = Field(default=None, max_length=300)
    objectives: str | None = Field(default=None, max_length=400)
    voice: str | None = Field(default=None, max_length=20)
    start_at: datetime | None = None
    end_at: datetime | None = None
