from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from creator.domain.pipeline_events import PipelineEvent
from creator.infrastructure import models
from creator.repositories.outbox import OutboxEventRecord


class SqlAlchemyOutboxRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, *, workspace_id: UUID, aggregate_id: UUID, event: PipelineEvent) -> UUID:
        row = models.OutboxEvent(
            workspace_id=workspace_id,
            aggregate_id=aggregate_id,
            event_type=event.event_type.value,
            event_version=event.event_version,
            payload=event.model_dump(mode="json"),
        )
        self._session.add(row)
        self._session.flush()
        return row.id

    def claim_batch(self, *, limit: int = 50) -> list[OutboxEventRecord]:
        now = datetime.now(UTC)
        rows = self._session.scalars(
            select(models.OutboxEvent)
            .where(
                models.OutboxEvent.published_at.is_(None),
                models.OutboxEvent.available_at <= now,
            )
            .order_by(models.OutboxEvent.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        ).all()
        for row in rows:
            row.attempts += 1
        return [_record(row) for row in rows]

    def mark_published(self, event_id: UUID) -> None:
        row = self._session.get(models.OutboxEvent, event_id)
        if row is not None:
            row.published_at = datetime.now(UTC)

    def mark_failed(self, event_id: UUID, error: str) -> None:
        row = self._session.get(models.OutboxEvent, event_id)
        if row is not None:
            row.last_error = error[:2_000]


def _record(row: models.OutboxEvent) -> OutboxEventRecord:
    return OutboxEventRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        aggregate_id=row.aggregate_id,
        event_type=row.event_type,
        event_version=row.event_version,
        payload=dict(row.payload),
        available_at=cast(datetime, row.available_at),
    )
