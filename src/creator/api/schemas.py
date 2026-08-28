from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Meta(BaseModel):
    request_id: UUID


class SuccessResponse(BaseModel):
    success: bool = True
    data: Any
    meta: Meta


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
    meta: Meta


class GenerateTextRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20_000)
    temperature: float = Field(default=0.7, ge=0, le=2)
