from uuid import UUID

from redis import Redis
from rq import Queue, Retry

from creator.config import Settings, get_settings


class RqGenerationQueue:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection = Redis.from_url(settings.redis_url)
        self._queue = Queue(
            settings.generation_queue_name,
            connection=self._connection,
            default_timeout=settings.image_generation_job_timeout_seconds,
        )

    def enqueue_image_generation(self, *, job_id: UUID, request_id: UUID) -> object:
        retry_intervals = list(self._settings.image_generation_retry_interval_seconds)
        return self._queue.enqueue(
            "creator.workers.image_generation.run_image_generation",
            str(job_id),
            str(request_id),
            job_id=f"image-generation:{job_id}",
            job_timeout=self._settings.image_generation_job_timeout_seconds,
            retry=Retry(
                max=max(self._settings.image_generation_job_max_attempts - 1, 0),
                interval=retry_intervals,
            ),
            meta={
                "request_id": str(request_id),
                "generation_job_id": str(job_id),
            },
        )


def get_generation_queue() -> RqGenerationQueue:
    return RqGenerationQueue(get_settings())
