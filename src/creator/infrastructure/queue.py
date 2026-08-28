from redis import Redis
from rq import Queue

from creator.config import get_settings


def get_generation_queue() -> Queue:
    connection = Redis.from_url(get_settings().redis_url)
    return Queue("generations", connection=connection, default_timeout=900)
