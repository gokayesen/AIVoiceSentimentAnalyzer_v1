"""RQ enqueue helper (AD-13). web-api only ever enqueues onto this queue — it
never imports ml-service pipeline code in-process (AD-7) and never runs an RQ
worker itself; `run_ingest` is referenced by import-path string so RQ resolves
it inside the ml-service worker process, not here.

`get_queue()` is a separate function (not inlined into `enqueue_ingest`)
specifically so tests can monkeypatch it to return a
`Queue(is_async=False, connection=FakeStrictRedis())` test double — no live
Redis needed, per AD-21's "independently runnable" testing standard. Story
1.10's delete endpoint also reuses `get_queue().connection` directly rather
than adding a second connection getter.

Story 1.10 (AD-12): `enqueue_ingest` pins the RQ job's own id to `call_id`
(rather than letting RQ assign a random one) so a delete request can find and
cancel this specific job deterministically via `Job.fetch(call_id, ...)` while
the Call is still `queued`. This is the *only* job in a Call's multi-stage
pipeline (ingest → acoustic → transcript → text-sentiment → fusion) whose id
web-api can know in advance — every downstream stage's own re-enqueue call
(inside ml-service, not here) still gets an RQ-assigned random id, which is
fine: once a Call reaches `processing`, deletion awaits the job's completion
via `Call.status` instead of trying to cancel it (see the story's Dev Notes).
"""

from __future__ import annotations

from redis import Redis
from rq import Queue

from app.config import INGEST_QUEUE_NAME, REDIS_URL


def get_queue() -> Queue:
    return Queue(INGEST_QUEUE_NAME, connection=Redis.from_url(REDIS_URL))


def enqueue_ingest(call_id: str) -> None:
    get_queue().enqueue("app.pipeline.ingest.run.run_ingest", call_id, job_id=call_id)
