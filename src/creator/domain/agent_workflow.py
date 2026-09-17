from __future__ import annotations

from enum import StrEnum


class AgentWorkflowStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_FOR_HUMAN_REVIEW = "WAITING_FOR_HUMAN_REVIEW"
    REFINING = "REFINING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class AgentWorkflowStepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentWorkflowStepRole(StrEnum):
    BUSINESS = "BUSINESS"
    PLANNER = "PLANNER"
    WRITER = "WRITER"
    ARTIST = "ARTIST"
    REVIEWER = "REVIEWER"
    DELIVERY = "DELIVERY"


class HumanReviewMode(StrEnum):
    AUTO = "AUTO"
    OPTIONAL = "OPTIONAL"


class WorkflowDecision(StrEnum):
    APPROVE = "APPROVE"
    REFINE = "REFINE"
    REJECT = "REJECT"


ALLOWED_AGENT_WORKFLOW_TRANSITIONS: dict[AgentWorkflowStatus, frozenset[AgentWorkflowStatus]] = {
    AgentWorkflowStatus.PENDING: frozenset({AgentWorkflowStatus.RUNNING}),
    AgentWorkflowStatus.RUNNING: frozenset(
        {
            AgentWorkflowStatus.WAITING_FOR_HUMAN_REVIEW,
            AgentWorkflowStatus.REFINING,
            AgentWorkflowStatus.COMPLETED,
            AgentWorkflowStatus.REJECTED,
            AgentWorkflowStatus.FAILED,
        }
    ),
    AgentWorkflowStatus.WAITING_FOR_HUMAN_REVIEW: frozenset(
        {AgentWorkflowStatus.REFINING, AgentWorkflowStatus.COMPLETED, AgentWorkflowStatus.REJECTED}
    ),
    AgentWorkflowStatus.REFINING: frozenset(
        {
            AgentWorkflowStatus.RUNNING,
            AgentWorkflowStatus.FAILED,
            AgentWorkflowStatus.WAITING_FOR_HUMAN_REVIEW,
            AgentWorkflowStatus.COMPLETED,
            AgentWorkflowStatus.REJECTED,
        }
    ),
    AgentWorkflowStatus.COMPLETED: frozenset(),
    AgentWorkflowStatus.REJECTED: frozenset(),
    AgentWorkflowStatus.FAILED: frozenset(),
}


def can_transition_agent_workflow(
    current: AgentWorkflowStatus, target: AgentWorkflowStatus
) -> bool:
    return target in ALLOWED_AGENT_WORKFLOW_TRANSITIONS[current]
