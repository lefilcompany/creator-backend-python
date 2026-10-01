from __future__ import annotations

import logging
from typing import Any

from creator.config import get_settings
from creator.domain.pipeline_events import PipelineEvent, PipelineEventType
from creator.infrastructure.queue import RqGenerationQueue
from creator.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from creator.services.agents.event_publisher import OutboxPublisher
from creator.workers.agent_workflow import run_image_agent_workflow

logger = logging.getLogger(__name__)


def handle_pipeline_event(payload: dict[str, Any]) -> None:
    """Entry point for the event queue during the staged migration."""
    event = PipelineEvent.model_validate(payload)
    if event.event_type == PipelineEventType.WORKFLOW_STARTED:
        run_image_agent_workflow(str(event.run_id), str(event.correlation_id), stage="BUSINESS")
        return
    if event.event_type == PipelineEventType.BUSINESS_COMPLETED:
        run_image_agent_workflow(str(event.run_id), str(event.correlation_id), stage="PLANNER")
        return
    if event.event_type == PipelineEventType.PLANNER_COMPLETED:
        run_image_agent_workflow(str(event.run_id), str(event.correlation_id), stage="WRITER")
        return
    if event.event_type == PipelineEventType.WRITER_COMPLETED:
        run_image_agent_workflow(str(event.run_id), str(event.correlation_id), stage="ARTIST")
        return
    if event.event_type == PipelineEventType.ARTIST_COMPLETED:
        run_image_agent_workflow(str(event.run_id), str(event.correlation_id), stage="REVIEWER")
        return
    if event.event_type == PipelineEventType.WRITER_REFINEMENT_REQUESTED:
        run_image_agent_workflow(str(event.run_id), str(event.correlation_id), stage="WRITER")
        return
    logger.info(
        "pipeline_event_waiting_for_stage_consumer",
        extra={"event_id": str(event.event_id), "event_type": event.event_type.value},
    )


def publish_pipeline_outbox_once(limit: int = 50) -> int:
    with SqlAlchemyUnitOfWork() as unit_of_work:
        published = OutboxPublisher(unit_of_work, RqGenerationQueue(get_settings())).publish_once(
            limit=limit
        )
        return published
