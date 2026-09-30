from pydantic import Field

from ..base import CreatorDTO


class AuthLoginRequest(CreatorDTO):
    email: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=4096, repr=False)
