from __future__ import annotations

from uuid import UUID

from creator.config import Settings
from creator.infrastructure import queue


class FakeRedis:
    @classmethod
    def from_url(cls, url: str) -> str:
        return f"connection:{url}"


class FakeQueue:
    def __init__(self, name: str, *, connection: object, default_timeout: int) -> None:
        self.name = name
        self.connection = connection
        self.default_timeout = default_timeout
        self.calls: list[dict[str, object]] = []

    def enqueue(self, f: str, *args: object, **kwargs: object) -> object:
        self.calls.append({"f": f, "args": args, **kwargs})
        return object()


class FakeRetry:
    def __init__(self, *, max: int, interval: list[int]) -> None:
        self.max = max
        self.interval = interval


def test_rq_generation_queue_enqueues_image_job_with_retry_policy(
    monkeypatch,
) -> None:
    queues: list[FakeQueue] = []

    def fake_queue(name: str, *, connection: object, default_timeout: int) -> FakeQueue:
        created = FakeQueue(name, connection=connection, default_timeout=default_timeout)
        queues.append(created)
        return created

    monkeypatch.setattr(queue, "Redis", FakeRedis)
    monkeypatch.setattr(queue, "Queue", fake_queue)
    monkeypatch.setattr(queue, "Retry", FakeRetry)
    settings = Settings(
        _env_file=None,
        redis_url="redis://redis:6379/0",
        generation_queue_name="creator:rq:generations",
        image_generation_job_timeout_seconds=123,
        image_generation_job_max_attempts=4,
        image_generation_retry_interval_seconds=[10, 20, 40],
    )
    job_id = UUID("50000000-0000-0000-0000-000000000001")
    request_id = UUID("70000000-0000-0000-0000-000000000001")

    queue.RqGenerationQueue(settings).enqueue_image_generation(
        job_id=job_id,
        request_id=request_id,
    )

    created = queues[0]
    call = created.calls[0]
    assert created.name == "creator:rq:generations"
    assert created.connection == "connection:redis://redis:6379/0"
    assert created.default_timeout == 123
    assert call["f"] == "creator.workers.image_generation.run_image_generation"
    assert call["args"] == (str(job_id), str(request_id))
    assert call["job_id"] == f"creator:rq:image-generation:{job_id}"
    assert call["job_timeout"] == 123
    assert call["meta"] == {
        "request_id": str(request_id),
        "generation_job_id": str(job_id),
    }
    retry = call["retry"]
    assert retry.max == 3
    assert retry.interval == [10, 20, 40]
