from __future__ import annotations

import argparse
import logging

from redis import Redis
from rq import Queue, Worker

from creator.config import get_settings
from creator.workers.image_generation import recover_stale_processing_jobs


def main() -> None:
    parser = argparse.ArgumentParser(prog="creator-worker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("image-generation")
    subparsers.add_parser("agent-workflow")
    args = parser.parse_args()

    logging.basicConfig(level=get_settings().log_level)
    if args.command == "image-generation":
        run_image_generation_worker()
    elif args.command == "agent-workflow":
        run_agent_workflow_worker()


def run_image_generation_worker() -> None:
    settings = get_settings()
    recover_stale_processing_jobs()
    connection = Redis.from_url(settings.redis_url)
    queue = Queue(settings.generation_queue_name, connection=connection)
    Worker([queue], connection=connection).work(with_scheduler=True)


def run_agent_workflow_worker() -> None:
    settings = get_settings()
    connection = Redis.from_url(settings.redis_url)
    queue = Queue(settings.generation_queue_name, connection=connection)
    Worker([queue], connection=connection).work(with_scheduler=True)
