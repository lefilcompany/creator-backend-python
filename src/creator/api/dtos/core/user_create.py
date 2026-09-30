from typing import Literal

from pydantic import Field

from ..base import CreatorDTO


class UserCreateRequest(CreatorDTO):
    external_id: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=50)
    display_name: str | None = Field(default=None, max_length=50)
    global_role: Literal["admin", "gestor", "membro"] = "membro"
