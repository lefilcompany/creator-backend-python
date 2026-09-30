from typing import Literal

from pydantic import Field

from ..base import CreatorDTO


class ImageWorkflowDecisionRequest(CreatorDTO):
    decision: Literal["APPROVE", "REFINE", "REJECT"]
    feedback: str | None = Field(default=None, max_length=4_000)
