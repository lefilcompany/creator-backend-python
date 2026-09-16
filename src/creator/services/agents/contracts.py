from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from creator.domain.agent_workflow import AgentWorkflowStepRole


class BusinessOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brand_summary: str = Field(min_length=1, max_length=4_000)
    voice: str = Field(min_length=1, max_length=2_000)
    visual_direction: str = Field(min_length=1, max_length=4_000)
    constraints: list[str] = Field(default_factory=list, max_length=30)
    knowledge_sources: list[str] = Field(default_factory=list, max_length=30)


class PlannedPost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: str = Field(min_length=1, max_length=500)
    objective: str = Field(min_length=1, max_length=1_000)
    big_idea: str = Field(min_length=1, max_length=1_000)
    main_message: str = Field(min_length=1, max_length=2_000)


class PlannerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    posts: list[PlannedPost] = Field(min_length=1, max_length=20)


class DesignDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    briefing: str = Field(min_length=1, max_length=5_000)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    copy_text: str = Field(alias="copy", min_length=1, max_length=2_000)
    visual_prompt: str = Field(min_length=1, max_length=20_000)


class WriterOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caption: str = Field(min_length=1, max_length=4_000)
    direction: DesignDirection


class ReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(pattern="^(APPROVED|REFINE|REJECTED)$")
    score: float = Field(ge=0, le=1)
    brand_adherence: float = Field(ge=0, le=1)
    brief_adherence: float = Field(ge=0, le=1)
    technical_quality: float = Field(ge=0, le=1)
    safety_issues: list[str] = Field(default_factory=list, max_length=30)
    feedback: list[str] = Field(default_factory=list, max_length=30)


@dataclass(frozen=True, slots=True)
class AgentExecutionContext:
    workspace_id: UUID
    brand_id: UUID
    role: AgentWorkflowStepRole
    inputs: Mapping[str, object]
    prompt_template_id: str
    prompt_template_version: str


@dataclass(frozen=True, slots=True)
class AgentExecutionResult:
    output: BaseModel
    prompt: str
    input_hash: str
    provider: str
    model: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class SpecialistAgent(Protocol):
    role: AgentWorkflowStepRole

    def execute(self, context: AgentExecutionContext) -> AgentExecutionResult: ...
