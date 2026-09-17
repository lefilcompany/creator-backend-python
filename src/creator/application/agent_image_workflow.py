from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from creator.application.unit_of_work import UnitOfWork
from creator.config import Settings
from creator.domain.agent_workflow import AgentWorkflowStatus, HumanReviewMode, WorkflowDecision
from creator.domain.exceptions import EntityNotFoundError
from creator.prompts.base import normalize_json_object
from creator.repositories import AgentWorkflowRunRecord, UserRecord


class AgentWorkflowQueue(Protocol):
    def enqueue_agent_workflow(self, *, run_id: UUID, request_id: UUID) -> object: ...


class AgentWorkflowInputError(ValueError):
    """Raised when a workflow request cannot be safely executed."""


class AgentWorkflowIdempotencyConflictError(ValueError):
    """Raised when an idempotency key is reused for a different input."""


class AgentWorkflowDecisionError(ValueError):
    """Raised when a human decision is invalid for the current run."""


@dataclass(frozen=True, slots=True)
class StartImageWorkflowCommand:
    brand_id: UUID
    campaign: str
    persona: str
    quantity: int
    extra_instructions: str | None
    human_review: str
    max_refinements: int | None
    extensions: Mapping[str, object]
    idempotency_key: str
    request_id: UUID


def start_image_workflow(
    *,
    unit_of_work: UnitOfWork,
    queue: AgentWorkflowQueue,
    settings: Settings,
    user: UserRecord,
    command: StartImageWorkflowCommand,
) -> AgentWorkflowRunRecord:
    brand = unit_of_work.brands.get_for_user(user_id=user.id, brand_id=command.brand_id)
    if brand is None:
        raise EntityNotFoundError("Brand not found")
    existing = unit_of_work.agent_workflows.get_by_idempotency(
        user_id=user.id,
        workspace_id=brand.workspace_id,
        idempotency_key=command.idempotency_key,
    )
    input_payload = normalize_json_object(
        {
            "brand_id": str(command.brand_id),
            "campaign": command.campaign,
            "persona": command.persona,
            "quantity": command.quantity,
            "extra_instructions": command.extra_instructions,
            "human_review": command.human_review,
            "max_refinements": command.max_refinements,
            "extensions": dict(command.extensions),
        }
    )
    fingerprint = _fingerprint(input_payload)
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise AgentWorkflowIdempotencyConflictError("Workflow idempotency key was reused")
        return existing

    configured_max = settings.agent_workflow_max_refinements
    max_refinements = configured_max if command.max_refinements is None else command.max_refinements
    if max_refinements > configured_max:
        raise AgentWorkflowInputError("max_refinements exceeds the configured workflow limit")

    content = unit_of_work.contents.add(
        workspace_id=brand.workspace_id,
        created_by_user_id=user.id,
        content_type="IMAGE",
        brand_id=brand.id,
        title=command.campaign[:255],
        payload={
            "workflow_status": "PENDING",
            "workflow_input": input_payload,
        },
    )
    run = unit_of_work.agent_workflows.create_run(
        user_id=user.id,
        workspace_id=brand.workspace_id,
        content_id=content.id,
        brand_id=brand.id,
        idempotency_key=command.idempotency_key,
        request_fingerprint=fingerprint,
        input=dict(input_payload),
        human_review=HumanReviewMode(command.human_review),
        max_refinements=max_refinements,
    )
    unit_of_work.commit()
    try:
        queue.enqueue_agent_workflow(run_id=run.id, request_id=command.request_id)
    except Exception as error:
        raise AgentWorkflowQueueError("Image agent workflow could not be queued") from error
    return run


class AgentWorkflowQueueError(RuntimeError):
    """Raised when a workflow run cannot be submitted to the queue."""


def decide_image_workflow(
    *,
    unit_of_work: UnitOfWork,
    queue: AgentWorkflowQueue,
    run_id: UUID,
    user: UserRecord,
    request_id: UUID,
    decision: WorkflowDecision,
    feedback: str | None,
) -> AgentWorkflowRunRecord:
    run = unit_of_work.agent_workflows.get_for_user(user_id=user.id, run_id=run_id)
    if run is None:
        raise EntityNotFoundError("Agent workflow not found")
    if run.status != AgentWorkflowStatus.WAITING_FOR_HUMAN_REVIEW:
        raise AgentWorkflowDecisionError("Workflow is not waiting for human review")
    if decision == WorkflowDecision.REFINE and not feedback:
        raise AgentWorkflowDecisionError("Feedback is required to refine a workflow")
    if decision == WorkflowDecision.APPROVE:
        updated = unit_of_work.agent_workflows.transition(
            run_id, AgentWorkflowStatus.COMPLETED, current_step="DELIVERY"
        )
        unit_of_work.commit()
        return updated
    if decision == WorkflowDecision.REJECT:
        updated = unit_of_work.agent_workflows.transition(
            run_id, AgentWorkflowStatus.REJECTED, current_step="DELIVERY"
        )
        unit_of_work.commit()
        return updated

    if run.refinement_count >= run.max_refinements:
        raise AgentWorkflowDecisionError("Maximum workflow refinements reached")
    updated_input = dict(run.input)
    updated_input["human_feedback"] = feedback
    unit_of_work.agent_workflows.update_input(run_id, updated_input)
    updated = unit_of_work.agent_workflows.transition(
        run_id,
        AgentWorkflowStatus.REFINING,
        current_step="WRITER",
        refinement_count=run.refinement_count + 1,
    )
    unit_of_work.commit()
    try:
        queue.enqueue_agent_workflow(run_id=run_id, request_id=request_id)
    except Exception as error:
        raise AgentWorkflowQueueError("Refined image agent workflow could not be queued") from error
    return updated


def _fingerprint(payload: Mapping[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
