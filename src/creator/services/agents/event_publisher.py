from __future__ import annotations

from typing import Protocol
from uuid import UUID

from creator.application.unit_of_work import UnitOfWork
from creator.domain.pipeline_events import PipelineEvent


class PipelineEventTransport(Protocol):
    def enqueue_pipeline_event(self, *, event_id: UUID, event: PipelineEvent) -> object: ...


class OutboxPublisher:
    """Publishes committed events and leaves failed rows available for retry."""

    def __init__(self, unit_of_work: UnitOfWork, transport: PipelineEventTransport) -> None:
        self._unit_of_work = unit_of_work
        self._transport = transport

    def publish_once(self, *, limit: int = 50) -> int:
        events = self._unit_of_work.outbox.claim_batch(limit=limit)
        published = 0
        for record in events:
            try:
                event = PipelineEvent.model_validate(record.payload)
                self._transport.enqueue_pipeline_event(event_id=record.id, event=event)
            except Exception as error:
                self._unit_of_work.outbox.mark_failed(record.id, str(error))
                continue
            self._unit_of_work.outbox.mark_published(record.id)
            published += 1
        self._unit_of_work.commit()
        return published
