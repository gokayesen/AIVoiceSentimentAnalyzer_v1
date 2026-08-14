"""RQ worker entrypoint (AD-13). Initializes the shared SQLite schema
(idempotent) before consuming jobs, since container startup order between
web-api and ml-service is not guaranteed by docker-compose."""

from __future__ import annotations

from redis import Redis
from rq import Worker

from app import db
from app.config import (
    ACOUSTIC_QUEUE_NAME,
    FUSION_QUEUE_NAME,
    INGEST_QUEUE_NAME,
    REDIS_URL,
    TEXT_SENTIMENT_QUEUE_NAME,
    TRANSCRIPT_QUEUE_NAME,
)
from app.logging_config import configure_logging


def main() -> None:
    configure_logging()
    db.init_db()
    connection = Redis.from_url(REDIS_URL)
    # Story 1.6: one consolidated worker process consumes all five stages
    # (AD-7) — ingest chains into acoustic chains into transcript chains
    # into text-sentiment, which (along with several earlier-stage failure
    # paths, see fusion/run.py) chains into fusion, each via the queue
    # (AD-13).
    worker = Worker(
        [
            INGEST_QUEUE_NAME,
            ACOUSTIC_QUEUE_NAME,
            TRANSCRIPT_QUEUE_NAME,
            TEXT_SENTIMENT_QUEUE_NAME,
            FUSION_QUEUE_NAME,
        ],
        connection=connection,
    )
    worker.work()


if __name__ == "__main__":
    main()
