from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from creator.domain.pipeline_events import PipelineEvent


@dataclass(frozen=True, slots=True)
class OutboxEventRecord:
    id: UUID
    workspace_id: UUID
    aggregate_id: UUID
    event_type: str
    event_version: str
    payload: dict[str, object]
    available_at: datetime


class OutboxRepository(Protocol):
    def add(self, *, workspace_id: UUID, aggregate_id: UUID, event: PipelineEvent) -> UUID: ...

    def claim_batch(self, *, limit: int = 50) -> list[OutboxEventRecord]: ...

    def mark_published(self, event_id: UUID) -> None: ...

    def mark_failed(self, event_id: UUID, error: str) -> None: ...
