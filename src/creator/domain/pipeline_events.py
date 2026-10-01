from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PipelineEventType(StrEnum):
    WORKFLOW_STARTED = "WorkflowStarted"
    BUSINESS_COMPLETED = "BusinessCompleted"
    PLANNER_COMPLETED = "PlannerCompleted"
    WRITER_COMPLETED = "WriterCompleted"
    ARTIST_COMPLETED = "ArtistCompleted"
    REVIEWER_COMPLETED = "ReviewerCompleted"
    WRITER_REFINEMENT_REQUESTED = "WriterRefinementRequested"


class PipelineEvent(BaseModel):
    """Durable event envelope; the payload remains in the workflow step."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_type: PipelineEventType
    event_version: str = Field(pattern=r"^1\.0$")
    workspace_id: UUID
    run_id: UUID
    step_id: UUID | None = None
    predecessor_step_id: UUID | None = None
    correlation_id: UUID
    input_hash: str | None = Field(default=None, min_length=64, max_length=64)
    output_hash: str | None = Field(default=None, min_length=64, max_length=64)
    payload_ref: dict[str, Any] = Field(default_factory=dict)
