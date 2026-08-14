"""RQ queue accessor(s) — a thin indirection point so tests can monkeypatch
the connection without a live Redis server, mirroring web-api/app/queue.py's
established pattern (Story 1.2). Story 1.3 introduces the first intra-service
stage-chaining enqueue (ingest -> acoustic, AD-13)."""

from __future__ import annotations

from redis import Redis
from rq import Queue

from app.config import (
    ACOUSTIC_QUEUE_NAME,
    FUSION_QUEUE_NAME,
    REDIS_URL,
    TEXT_SENTIMENT_QUEUE_NAME,
    TRANSCRIPT_QUEUE_NAME,
)


def get_acoustic_queue() -> Queue:
    return Queue(ACOUSTIC_QUEUE_NAME, connection=Redis.from_url(REDIS_URL))


def get_transcript_queue() -> Queue:
    return Queue(TRANSCRIPT_QUEUE_NAME, connection=Redis.from_url(REDIS_URL))


def get_text_sentiment_queue() -> Queue:
    return Queue(TEXT_SENTIMENT_QUEUE_NAME, connection=Redis.from_url(REDIS_URL))


def get_fusion_queue() -> Queue:
    return Queue(FUSION_QUEUE_NAME, connection=Redis.from_url(REDIS_URL))
