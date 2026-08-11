import logging

from fastapi import APIRouter, Request, status

from app.schemas import EventAccepted, EventIn
from app.services.event_service import enqueue_event

router = APIRouter(prefix="/events", tags=["events"])
logger = logging.getLogger(__name__)


@router.post("", response_model=EventAccepted, status_code=status.HTTP_202_ACCEPTED)
def ingest_event(event: EventIn, request: Request) -> EventAccepted:
    """Accepts one event, validates it (Pydantic, before this line even runs),
    and enqueues it to SQS. Deliberately does NOT touch Postgres/S3/Redis —
    that work happens asynchronously in the worker so ingestion latency stays
    flat regardless of downstream load. Returns 202, not 200/201: the event
    is accepted for processing, not yet processed."""
    request_id = getattr(request.state, "request_id", "-")
    event_id = enqueue_event(event, request_id)
    return EventAccepted(event_id=event_id)
