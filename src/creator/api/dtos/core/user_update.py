from typing import Literal

from pydantic import Field

from ..base import CreatorDTO


class UserUpdateRequest(CreatorDTO):
    email: str | None = Field(default=None, max_length=50)
    display_name: str | None = Field(default=None, max_length=50)
    global_role: Literal["admin", "gestor", "membro"] | None = None
