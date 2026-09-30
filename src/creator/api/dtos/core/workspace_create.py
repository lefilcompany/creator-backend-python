from pydantic import Field

from ..base import CreatorDTO


class WorkspaceCreateRequest(CreatorDTO):
    name: str = Field(min_length=1, max_length=50)
