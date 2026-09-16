from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from creator.domain.agent_workflow import (
    AgentWorkflowStatus,
    AgentWorkflowStepRole,
    AgentWorkflowStepStatus,
    HumanReviewMode,
)
from creator.repositories.common import JsonObject


@dataclass(frozen=True, slots=True)
class AgentWorkflowRunRecord:
    id: UUID
    workspace_id: UUID
    content_id: UUID
    brand_id: UUID
    requested_by_user_id: UUID | None
    idempotency_key: str
    request_fingerprint: str
    status: AgentWorkflowStatus
    human_review: HumanReviewMode
    max_refinements: int
    refinement_count: int
    current_step: str | None
    input: JsonObject
    final_image_ids: list[str]
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class AgentWorkflowStepRecord:
    id: UUID
    run_id: UUID
    workspace_id: UUID
    sequence_number: int
    role: AgentWorkflowStepRole
    status: AgentWorkflowStepStatus
    attempt: int
    input: JsonObject
    output: JsonObject
    prompt: str | None
    prompt_template_id: str | None
    prompt_template_version: str | None
    input_hash: str | None
    provider: str | None
    model: str | None
    decision: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class AgentWorkflowRepository(Protocol):
    def create_run(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        content_id: UUID,
        brand_id: UUID,
        idempotency_key: str,
        request_fingerprint: str,
        input: JsonObject,
        human_review: HumanReviewMode,
        max_refinements: int,
    ) -> AgentWorkflowRunRecord: ...

    def get_for_user(self, *, user_id: UUID, run_id: UUID) -> AgentWorkflowRunRecord | None: ...

    def get_by_idempotency(
        self, *, user_id: UUID, workspace_id: UUID, idempotency_key: str
    ) -> AgentWorkflowRunRecord | None: ...

    def get_internal(self, run_id: UUID) -> AgentWorkflowRunRecord | None: ...

    def list_steps_for_user(
        self, *, user_id: UUID, run_id: UUID
    ) -> list[AgentWorkflowStepRecord] | None: ...

    def list_steps_internal(self, run_id: UUID) -> list[AgentWorkflowStepRecord]: ...

    def add_step(
        self,
        *,
        run_id: UUID,
        workspace_id: UUID,
        sequence_number: int,
        role: AgentWorkflowStepRole,
        attempt: int,
        input: JsonObject,
    ) -> AgentWorkflowStepRecord: ...

    def complete_step(
        self,
        step_id: UUID,
        *,
        output: JsonObject,
        prompt: str | None = None,
        prompt_template_id: str | None = None,
        prompt_template_version: str | None = None,
        input_hash: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        decision: str | None = None,
    ) -> AgentWorkflowStepRecord: ...

    def fail_step(self, step_id: UUID, *, error_code: str, error_message: str) -> None: ...

    def transition(
        self,
        run_id: UUID,
        target: AgentWorkflowStatus,
        *,
        current_step: str | None = None,
        refinement_count: int | None = None,
        final_image_ids: list[str] | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> AgentWorkflowRunRecord: ...

    def update_input(self, run_id: UUID, input: JsonObject) -> AgentWorkflowRunRecord: ...
