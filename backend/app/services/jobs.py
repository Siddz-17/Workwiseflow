"""Background job dispatch: Redis + RQ when REDIS_URL is set, otherwise FastAPI BackgroundTasks."""

import logging

from fastapi import BackgroundTasks

from ..config import get_settings
from .ingestion import process_document

log = logging.getLogger(__name__)


def enqueue_ingestion(document_id: str, background: BackgroundTasks | None) -> str:
    url = get_settings().redis_url
    if url:
        from redis import Redis
        from rq import Queue

        Queue("ingestion", connection=Redis.from_url(url)).enqueue(
            "app.services.ingestion.process_document", document_id, job_timeout=900
        )
        return "queued"
    if background is not None:
        background.add_task(process_document, document_id)
        return "background"
    process_document(document_id)
    return "inline"
