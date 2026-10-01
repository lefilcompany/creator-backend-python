from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from creator.domain.pipeline_events import PipelineEvent, PipelineEventType
from creator.services.agents.event_publisher import OutboxPublisher


def _event() -> PipelineEvent:
    return PipelineEvent(
        event_id=uuid4(),
        event_type=PipelineEventType.WORKFLOW_STARTED,
        event_version="1.0",
        workspace_id=uuid4(),
        run_id=uuid4(),
        correlation_id=uuid4(),
    )


class FakeOutbox:
    def __init__(self, event: PipelineEvent) -> None:
        self.record = SimpleNamespace(
            id=uuid4(),
            payload=event.model_dump(mode="json"),
            available_at=datetime.now(UTC),
        )
        self.published: list[object] = []
        self.failed: list[tuple[object, str]] = []

    def claim_batch(self, *, limit: int = 50) -> list[object]:
        return [self.record][:limit]

    def mark_published(self, event_id: object) -> None:
        self.published.append(event_id)

    def mark_failed(self, event_id: object, error: str) -> None:
        self.failed.append((event_id, error))


class FakeUow:
    def __init__(self, outbox: FakeOutbox) -> None:
        self.outbox = outbox
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


class Transport:
    def __init__(self) -> None:
        self.events: list[PipelineEvent] = []

    def enqueue_pipeline_event(self, *, event_id: object, event: PipelineEvent) -> object:
        self.events.append(event)
        return event_id


def test_publisher_marks_valid_event_after_transport_publish() -> None:
    outbox = FakeOutbox(_event())
    transport = Transport()
    assert OutboxPublisher(FakeUow(outbox), transport).publish_once() == 1
    assert len(transport.events) == 1
    assert outbox.published
    assert not outbox.failed


def test_publisher_keeps_failed_event_retryable() -> None:
    outbox = FakeOutbox(_event())

    class FailingTransport(Transport):
        def enqueue_pipeline_event(self, **kwargs: object) -> object:
            raise RuntimeError("broker unavailable")

    assert OutboxPublisher(FakeUow(outbox), FailingTransport()).publish_once() == 0
    assert outbox.failed
    assert not outbox.published
